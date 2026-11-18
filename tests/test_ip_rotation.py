import importlib.machinery
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


telegram = types.ModuleType('telegram')
telegram.Update = type('Update', (), {})
class InlineKeyboardButton:
    def __init__(self, text, callback_data):
        self.text = text
        self.callback_data = callback_data


class InlineKeyboardMarkup:
    def __init__(self, inline_keyboard):
        self.inline_keyboard = inline_keyboard


telegram.InlineKeyboardButton = InlineKeyboardButton
telegram.InlineKeyboardMarkup = InlineKeyboardMarkup
telegram_ext = types.ModuleType('telegram.ext')
for name in ('Updater', 'CommandHandler', 'CallbackContext', 'CallbackQueryHandler', 'MessageHandler'):
    setattr(telegram_ext, name, type(name, (), {}))
telegram_ext.Filters = type('Filters', (), {})
dispatcher = types.ModuleType('telegram.ext.dispatcher')
dispatcher.run_async = lambda func: func
sys.modules['telegram'] = telegram
sys.modules['telegram.ext'] = telegram_ext
sys.modules['telegram.ext.dispatcher'] = dispatcher

source = Path(__file__).resolve().parents[1] / 'traffic_control.py.template'
loader = importlib.machinery.SourceFileLoader('traffic_control_test', str(source))
spec = importlib.util.spec_from_loader(loader.name, loader)
app = importlib.util.module_from_spec(spec)
loader.exec_module(app)
real_verify_cf_zone = app.verify_cf_zone

ACCOUNT = {
    'name': 'test-hk', 'instance_id': 'i-test', 'region_id': 'cn-hongkong',
    'cf_domain': 'hk.example.com', 'cf_zone_id': 'a' * 32,
    'cf_api_token': 'test-token',
}
OLD = {
    'AllocationId': 'eip-old', 'IpAddress': '198.51.100.10',
    'Status': 'InUse', 'InstanceId': 'i-test', 'InstanceType': 'EcsInstance',
    'ChargeType': 'PostPaid', 'InternetChargeType': 'PayByTraffic',
    'Bandwidth': '5', 'ISP': 'BGP',
}


class RotationTests(unittest.TestCase):
    def setUp(self):
        zone_patch = patch.object(app, 'verify_cf_zone', return_value='example.com')
        zone_patch.start()
        self.addCleanup(zone_patch.stop)

    def test_bot_menu_registers_current_commands(self):
        response = Mock(ok=True)
        response.json.return_value = {'ok': True}
        with (patch.object(app, 'ADMIN_USER_ID', '1234'),
              patch.object(app.requests, 'post', return_value=response) as post):
            app.register_bot_menu()
        self.assertEqual(post.call_count, 5)
        commands = post.call_args_list[0].kwargs['json']['commands']
        self.assertIn('changeip', [command['command'] for command in commands])
        self.assertIn('cfconfig', [command['command'] for command in commands])

    def test_cf_config_field_can_be_replaced(self):
        context = Mock(user_data={})
        context.user_data = {}
        update = Mock()
        update.callback_query.data = 'ip:field:0:zone'
        update.callback_query.message.chat_id = 123
        with (patch.object(app, 'is_admin', return_value=True),
              patch.object(app, 'load_accounts', return_value=[ACCOUNT]),
              patch.object(app, 'save_cf_setting') as save):
            app.ip_callback(update, context)
            self.assertEqual(context.user_data['ip_edit']['field'], 'cf_zone_id')
            update.message.text = 'b' * 32
            update.effective_chat.id = 123
            app.ip_setup_message(update, context)
            save.assert_called_once_with(ACCOUNT, 'cf_zone_id', 'b' * 32)
        self.assertNotIn('ip_edit', context.user_data)
        self.assertIn('API 令牌：已设置', context.bot.send_message.call_args.kwargs['text'])

    def test_cancel_clears_pending_input(self):
        context = Mock(user_data={})
        context.user_data = {'ip_edit': {'field': 'cf_zone_id'}, 'ip_targets': ['i-test']}
        update = Mock()
        with patch.object(app, 'is_admin', return_value=True):
            app.cancel_command(update, context)
        self.assertEqual(context.user_data, {})

    def test_failed_cf_preflight_does_not_offer_confirm(self):
        key = app.account_key(ACCOUNT)
        context = Mock(user_data={})
        context.user_data = {'ip_setup': {'keys': [key], 'index': 0}, 'ip_targets': [key]}
        with (patch.object(app, 'find_account', return_value=ACCOUNT),
              patch.object(app, 'load_accounts', return_value=[ACCOUNT]),
              patch.object(app, 'verify_cf_zone', side_effect=ValueError('wrong zone'))):
            app.prompt_ip_setup(context, 123)
        self.assertNotIn('ip_targets', context.user_data)
        self.assertIn('校验失败', context.bot.send_message.call_args.kwargs['text'])

    def test_current_eip_rejects_fixed_public_ip(self):
        with patch.object(app, 'vpc_action', return_value={'EipAddresses': {'EipAddress': []}}) as vpc:
            with self.assertRaisesRegex(ValueError, '固定公网 IP'):
                app.current_eip(ACCOUNT)
            self.assertEqual(vpc.call_args.kwargs['AssociatedInstanceId'], 'i-test')

    def test_current_eip_reports_ram_permission(self):
        with patch.object(app, 'vpc_action', side_effect=RuntimeError('Forbidden.RAM')):
            with self.assertRaisesRegex(ValueError, 'vpc:DescribeEipAddresses'):
                app.current_eip(ACCOUNT)

    def test_zone_mismatch_is_rejected(self):
        with patch.object(app, 'cf_request', return_value={'result': {'name': 'other.xyz'}}):
            with self.assertRaisesRegex(ValueError, '不属于'):
                real_verify_cf_zone(ACCOUNT)

    def test_wrong_zone_stops_before_aliyun_call(self):
        with (patch.object(app, 'verify_cf_zone', side_effect=ValueError('wrong zone')),
              patch.object(app, 'current_eip') as current):
            with self.assertRaisesRegex(ValueError, 'wrong zone'):
                app.rotate_one_eip(ACCOUNT)
            current.assert_not_called()

    def test_dns_mismatch_stops_before_allocation(self):
        with (patch.object(app, 'current_eip', return_value=OLD),
              patch.object(app, 'cf_record', return_value={'id': 'dns-1', 'content': '203.0.113.9'}),
              patch.object(app, 'vpc_action') as vpc):
            with self.assertRaisesRegex(ValueError, '不一致'):
                app.rotate_one_eip(ACCOUNT)
            vpc.assert_not_called()

    def test_success_allocates_before_unbind_and_releases_last(self):
        calls = []
        record = {'id': 'dns-1', 'content': OLD['IpAddress']}

        def vpc(_account, action, **kwargs):
            calls.append(action)
            if action == 'AllocateEipAddress':
                self.assertEqual(kwargs['Bandwidth'], '5')
                self.assertEqual(kwargs['InternetChargeType'], 'PayByTraffic')
                return {'AllocationId': 'eip-new', 'EipAddress': '198.51.100.20'}
            return {}

        def cf(_account, method, path, **kwargs):
            calls.append(method)
            if method == 'PATCH':
                record['content'] = kwargs['json']['content']
            return {}

        with (patch.object(app, 'current_eip', return_value=OLD),
              patch.object(app, 'cf_record', return_value=record),
              patch.object(app, 'vpc_action', side_effect=vpc),
              patch.object(app, 'cf_request', side_effect=cf),
              patch.object(app, 'wait_eip', return_value={})):
            result = app.rotate_one_eip(ACCOUNT)
        self.assertIn('198.51.100.20', result)
        self.assertEqual(calls, [
            'AllocateEipAddress', 'UnassociateEipAddress',
            'AssociateEipAddress', 'PATCH', 'ReleaseEipAddress'
        ])

    def test_bind_failure_rebinds_old_and_releases_new(self):
        calls = []

        def vpc(_account, action, **kwargs):
            calls.append((action, kwargs.get('AllocationId')))
            if action == 'AllocateEipAddress':
                return {'AllocationId': 'eip-new', 'EipAddress': '198.51.100.20'}
            if action == 'AssociateEipAddress' and kwargs['AllocationId'] == 'eip-new':
                raise ValueError('bind failed')
            return {}

        with (patch.object(app, 'current_eip', return_value=OLD),
              patch.object(app, 'cf_record', return_value={'id': 'dns-1', 'content': OLD['IpAddress']}),
              patch.object(app, 'vpc_action', side_effect=vpc),
              patch.object(app, 'wait_eip', return_value={}),
              patch.object(app, 'describe_eip', return_value={'Status': 'Available'})):
            with self.assertRaisesRegex(RuntimeError, '旧 EIP 已重新绑定'):
                app.rotate_one_eip(ACCOUNT)
        self.assertIn(('AssociateEipAddress', 'eip-old'), calls)
        self.assertIn(('ReleaseEipAddress', 'eip-new'), calls)

    def test_dns_failure_preserves_old_eip(self):
        calls = []

        def vpc(_account, action, **kwargs):
            calls.append(action)
            if action == 'AllocateEipAddress':
                return {'AllocationId': 'eip-new', 'EipAddress': '198.51.100.20'}
            return {}

        with (patch.object(app, 'current_eip', return_value=OLD),
              patch.object(app, 'cf_record', return_value={'id': 'dns-1', 'content': OLD['IpAddress']}),
              patch.object(app, 'vpc_action', side_effect=vpc),
              patch.object(app, 'cf_request', side_effect=ValueError('dns failed')),
              patch.object(app, 'wait_eip', return_value={})):
            with self.assertRaisesRegex(RuntimeError, '旧 EIP 保留未释放'):
                app.rotate_one_eip(ACCOUNT)
        self.assertNotIn('ReleaseEipAddress', calls)

    def test_allocation_phase_failure_releases_unused_new_eip(self):
        calls = []

        def vpc(_account, action, **kwargs):
            calls.append(action)
            if action == 'AllocateEipAddress':
                return {'AllocationId': 'eip-new', 'EipAddress': '198.51.100.20'}
            return {}

        with (patch.object(app, 'current_eip', return_value=OLD),
              patch.object(app, 'cf_record', return_value={'id': 'dns-1', 'content': OLD['IpAddress']}),
              patch.object(app, 'vpc_action', side_effect=vpc),
              patch.object(app, 'wait_eip', side_effect=TimeoutError('not available')),
              patch.object(app, 'describe_eip', return_value={'Status': 'Available'})):
            with self.assertRaisesRegex(RuntimeError, '闲置新 EIP 已释放'):
                app.rotate_one_eip(ACCOUNT)
        self.assertEqual(calls, ['AllocateEipAddress', 'ReleaseEipAddress'])

    def test_uncertain_bind_keeps_new_eip_for_manual_check(self):
        calls = []

        def vpc(_account, action, **kwargs):
            calls.append(action)
            if action == 'AllocateEipAddress':
                return {'AllocationId': 'eip-new', 'EipAddress': '198.51.100.20'}
            if action == 'AssociateEipAddress':
                raise TimeoutError('request timeout')
            return {}

        with (patch.object(app, 'current_eip', return_value=OLD),
              patch.object(app, 'cf_record', return_value={'id': 'dns-1', 'content': OLD['IpAddress']}),
              patch.object(app, 'vpc_action', side_effect=vpc),
              patch.object(app, 'wait_eip', return_value={}),
              patch.object(app, 'describe_eip', return_value={'Status': 'Associating'})):
            with self.assertRaisesRegex(RuntimeError, '勿重复执行'):
                app.rotate_one_eip(ACCOUNT)
        self.assertNotIn('ReleaseEipAddress', calls)


if __name__ == '__main__':
    unittest.main()
