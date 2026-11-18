import importlib.machinery
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


telegram = types.ModuleType('telegram')
telegram.Update = type('Update', (), {})
telegram.InlineKeyboardButton = type('InlineKeyboardButton', (), {})
telegram.InlineKeyboardMarkup = type('InlineKeyboardMarkup', (), {})
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
    def test_bot_menu_registers_current_commands(self):
        response = Mock(ok=True)
        response.json.return_value = {'ok': True}
        with (patch.object(app, 'ADMIN_USER_ID', '1234'),
              patch.object(app.requests, 'post', return_value=response) as post):
            app.register_bot_menu()
        self.assertEqual(post.call_count, 5)
        commands = post.call_args_list[0].kwargs['json']['commands']
        self.assertIn('changeip', [command['command'] for command in commands])

    def test_current_eip_rejects_fixed_public_ip(self):
        with patch.object(app, 'vpc_action', return_value={'EipAddresses': {'EipAddress': []}}) as vpc:
            with self.assertRaisesRegex(ValueError, '固定公网 IP'):
                app.current_eip(ACCOUNT)
            self.assertEqual(vpc.call_args.kwargs['AssociatedInstanceId'], 'i-test')

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
