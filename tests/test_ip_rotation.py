import importlib.machinery
import importlib.util
import subprocess
import tempfile
import sys
import types
import unittest
from contextlib import nullcontext
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
    'access_key_id': 'test-id', 'access_key_secret': 'test-secret',
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
        self.assertIn('guide', [command['command'] for command in commands])

    def test_guide_sends_downloadable_file(self):
        context = Mock()
        update = Mock()
        guide = source.parent / 'GUIDE.md'
        with (patch.object(app, 'is_admin', return_value=True),
              patch.object(app, 'GUIDE_FILE', str(guide)),
              patch.object(app, 'get_chat_id', return_value=123)):
            app.guide_command(update, context)
        self.assertEqual(context.bot.send_document.call_args.kwargs['filename'], 'aliyun-cdt-guide.md')
        self.assertEqual(context.bot.send_document.call_args.kwargs['chat_id'], 123)

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

    def test_cf_zone_is_discovered_from_scoped_token(self):
        empty = Mock(ok=True)
        empty.json.return_value = {'success': True, 'result': []}
        found = Mock(ok=True)
        found.json.return_value = {'success': True, 'result': [{'name': 'example.com', 'id': 'b' * 32}]}
        with patch.object(app.requests, 'get', side_effect=[empty, found]) as get:
            zone_id = app.discover_cf_zone('hk.example.com', 'test-token')
        self.assertEqual(zone_id, 'b' * 32)
        self.assertEqual([call.kwargs['params']['name'] for call in get.call_args_list],
                         ['hk.example.com', 'example.com'])

    def test_cf_setup_auto_fills_zone_id(self):
        account = dict(ACCOUNT, cf_zone_id='')
        key = app.account_key(account)
        context = Mock(user_data={})
        context.user_data = {'ip_setup': {'keys': [key], 'index': 0}, 'ip_targets': [key]}

        def save(_account, field, value):
            account[field] = value

        with (patch.object(app, 'find_account', return_value=account),
              patch.object(app, 'discover_cf_zone', return_value='b' * 32),
              patch.object(app, 'save_cf_setting', side_effect=save)):
            app.prompt_ip_setup(context, 123)
        self.assertEqual(account['cf_zone_id'], 'b' * 32)
        self.assertNotIn('ip_setup', context.user_data)
        self.assertIn('确定执行', context.bot.send_message.call_args.kwargs['text'])

    def test_cf_setup_falls_back_to_manual_zone_id(self):
        account = dict(ACCOUNT, cf_zone_id='')
        key = app.account_key(account)
        context = Mock(user_data={})
        context.user_data = {'ip_setup': {'keys': [key], 'index': 0}, 'ip_targets': [key]}
        with (patch.object(app, 'find_account', return_value=account),
              patch.object(app, 'discover_cf_zone', side_effect=ValueError('缺少 Zone Read'))):
            app.prompt_ip_setup(context, 123)
        self.assertEqual(context.user_data['ip_setup']['field'], 'cf_zone_id')
        self.assertIn('缺少 Zone Read', context.bot.send_message.call_args.kwargs['text'])

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

    def test_bulk_preflight_requires_existing_matching_dns_record(self):
        with (patch.object(app, 'current_eip', return_value=OLD),
              patch.object(app, 'cf_record', return_value=None),
              patch.object(app, 'vpc_action') as vpc):
            with self.assertRaisesRegex(ValueError, '没有该域名的 A 记录'):
                app.preflight_rotation(ACCOUNT, require_record=True)
            vpc.assert_not_called()

    def test_bulk_skips_unconfigured_and_failed_accounts_without_setup(self):
        valid = dict(ACCOUNT)
        invalid = dict(ACCOUNT, name='missing-cf', instance_id='i-missing', cf_domain='')
        disabled = dict(ACCOUNT, name='disabled', instance_id='i-disabled', enabled=False)
        context = Mock(user_data={})
        context.user_data = {}
        update = Mock()
        update.callback_query.data = 'ip:all'
        update.callback_query.message.chat_id = 123

        def preflight(account, require_record=False):
            self.assertTrue(require_record)
            if account['name'] == 'missing-cf':
                raise ValueError('Cloudflare 域名格式不正确。')
            return OLD, {'id': 'dns-1', 'content': OLD['IpAddress']}

        with (patch.object(app, 'is_admin', return_value=True),
              patch.object(app, 'load_accounts', return_value=[valid, invalid, disabled]),
              patch.object(app, 'preflight_rotation', side_effect=preflight) as check,
              patch.object(app, 'prompt_ip_setup') as setup):
            app.ip_callback(update, context)
        setup.assert_not_called()
        self.assertEqual(check.call_count, 2)
        self.assertEqual(context.user_data['ip_targets'], [app.account_key(valid)])
        self.assertTrue(context.user_data['ip_bulk'])
        messages = [call.kwargs['text'] for call in context.bot.send_message.call_args_list]
        self.assertIn('missing-cf', messages[0])
        self.assertIn('预检通过 1 台', messages[1])
        self.assertNotIn('disabled', ''.join(messages))

    def test_bulk_all_failed_offers_no_confirm(self):
        context = Mock(user_data={})
        context.user_data = {}
        update = Mock()
        update.callback_query.data = 'ip:all'
        update.callback_query.message.chat_id = 123
        with (patch.object(app, 'is_admin', return_value=True),
              patch.object(app, 'load_accounts', return_value=[ACCOUNT]),
              patch.object(app, 'preflight_rotation', side_effect=ValueError('Forbidden.RAM'))):
            app.ip_callback(update, context)
        self.assertNotIn('ip_targets', context.user_data)
        self.assertIn('没有预检通过', context.bot.send_message.call_args.kwargs['text'])

    def test_bulk_confirm_skips_account_disabled_after_preflight(self):
        account = dict(ACCOUNT, enabled=False)
        key = app.account_key(account)
        context = Mock(user_data={})
        context.user_data = {'ip_targets': [key], 'ip_bulk': True}
        update = Mock()
        update.callback_query.data = 'ip:confirm'
        with (patch.object(app, 'is_admin', return_value=True),
              patch.object(app, 'find_account', return_value=account),
              patch.object(app, 'ip_rotation_lock', return_value=nullcontext()),
              patch.object(app, 'rotate_one_eip') as rotate):
            app.ip_callback(update, context)
        rotate.assert_not_called()
        self.assertIn('已禁用', update.callback_query.message.reply_text.call_args.args[0])

    def test_bulk_confirm_rechecks_and_skips_stale_dns(self):
        key = app.account_key(ACCOUNT)
        context = Mock(user_data={})
        context.user_data = {'ip_targets': [key], 'ip_bulk': True}
        update = Mock()
        update.callback_query.data = 'ip:confirm'
        with (patch.object(app, 'is_admin', return_value=True),
              patch.object(app, 'find_account', return_value=ACCOUNT),
              patch.object(app, 'ip_rotation_lock', return_value=nullcontext()),
              patch.object(app, 'preflight_rotation', side_effect=ValueError('DNS 已变化')),
              patch.object(app, 'rotate_one_eip') as rotate):
            app.ip_callback(update, context)
        rotate.assert_not_called()
        self.assertIn('预检未通过', update.callback_query.message.reply_text.call_args.args[0])

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

    def test_node_nftables_uses_new_ip_and_skips_installed_package(self):
        account = dict(ACCOUNT, node_ssh_host='hk.example.com', node_ssh_user='root',
                       node_ssh_port=22, node_ssh_key_path=str(source))
        completed = subprocess.CompletedProcess([], 0, 'NFT_PRESENT\nHOP_READY\n', '')
        with patch.object(app.subprocess, 'run', return_value=completed) as run:
            result = app.prepare_node_nftables(account, '198.51.100.20')
        self.assertIn('跳跃规则正常', result)
        command = run.call_args.args[0]
        self.assertIn('root@198.51.100.20', command)
        self.assertIn('HostKeyAlias=hk.example.com', command)
        self.assertIn('StrictHostKeyChecking=yes', command)
        self.assertIn('apk add --no-cache nftables', run.call_args.kwargs['input'])

    def test_node_nftables_reports_new_install(self):
        account = dict(ACCOUNT, node_ssh_host='hk.example.com', node_ssh_user='root',
                       node_ssh_port=22, node_ssh_key_path=str(source))
        completed = subprocess.CompletedProcess([], 0, 'NFT_INSTALLED\nHOP_READY\n', '')
        with patch.object(app.subprocess, 'run', return_value=completed):
            self.assertIn('已安装', app.prepare_node_nftables(account, '198.51.100.20'))

    def test_node_nftables_retries_new_ip_ssh_connection(self):
        account = dict(ACCOUNT, node_ssh_host='hk.example.com', node_ssh_user='root',
                       node_ssh_port=22, node_ssh_key_path=str(source))
        unavailable = subprocess.CompletedProcess([], 255, '', 'connection refused')
        ready = subprocess.CompletedProcess([], 0, 'NFT_PRESENT\nHOP_READY\n', '')
        with (patch.object(app.subprocess, 'run', side_effect=[unavailable, unavailable, ready]) as run,
              patch.object(app.time, 'sleep') as sleep):
            result = app.prepare_node_nftables(account, '198.51.100.20')
        self.assertIn('跳跃规则正常', result)
        self.assertEqual(run.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_node_ssh_setup_generates_per_account_key_and_saves_only_after_probe(self):
        account = dict(ACCOUNT)
        with tempfile.TemporaryDirectory() as tmp:
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                if command[0] == 'ssh-keygen':
                    Path(command[-1]).write_text('private', encoding='ascii')
                    Path(command[-1] + '.pub').write_text('ssh-ed25519 test public', encoding='ascii')
                return subprocess.CompletedProcess(command, 0)

            with (patch.object(app, 'NODE_SSH_DIR', tmp),
                  patch.object(app, 'get_selected_account_cli', return_value=account),
                  patch.object(app, 'prompt', side_effect=['hk.example.com', 'root', '22']),
                  patch.object(app.subprocess, 'run', side_effect=run),
                  patch.object(app, 'load_accounts', return_value=[account]),
                  patch.object(app, 'save_accounts') as save,
                  patch.object(app, 'current_eip', return_value=OLD),
                  patch.object(app, 'prepare_node_nftables', return_value='已安装')):
                app.setup_node_ssh_cli()
            self.assertEqual([cmd[0] for cmd in calls], ['ssh-keygen', 'ssh-copy-id', 'ssh'])
            self.assertEqual(account['node_ssh_host'], 'hk.example.com')
            self.assertTrue(account['node_ssh_key_path'].startswith(tmp))
            save.assert_called_once()

    def test_node_ssh_setup_does_not_save_failed_copy(self):
        account = dict(ACCOUNT)
        with tempfile.TemporaryDirectory() as tmp:
            def run(command, **kwargs):
                if command[0] == 'ssh-keygen':
                    Path(command[-1]).write_text('private', encoding='ascii')
                    Path(command[-1] + '.pub').write_text('ssh-ed25519 test public', encoding='ascii')
                return subprocess.CompletedProcess(command, 1 if command[0] == 'ssh-copy-id' else 0)

            with (patch.object(app, 'NODE_SSH_DIR', tmp),
                  patch.object(app, 'get_selected_account_cli', return_value=account),
                  patch.object(app, 'prompt', side_effect=['hk.example.com', 'root', '22']),
                  patch.object(app.subprocess, 'run', side_effect=run),
                  patch.object(app, 'save_accounts') as save):
                app.setup_node_ssh_cli()
            save.assert_not_called()

    def test_node_ssh_rejects_command_like_host(self):
        account = dict(ACCOUNT, node_ssh_host='-oProxyCommand=bad', node_ssh_key_path=str(source))
        with self.assertRaisesRegex(ValueError, 'SSH 地址'):
            app.validate_node_ssh(account)

    def test_node_nftables_failure_does_not_turn_rotation_into_failure(self):
        calls = []
        record = {'id': 'dns-1', 'content': OLD['IpAddress']}

        def vpc(_account, action, **kwargs):
            calls.append(action)
            if action == 'AllocateEipAddress':
                return {'AllocationId': 'eip-new', 'EipAddress': '198.51.100.20'}
            return {}

        def cf(_account, method, path, **kwargs):
            if method == 'PATCH':
                record['content'] = kwargs['json']['content']
            return {}

        with (patch.object(app, 'current_eip', return_value=OLD),
              patch.object(app, 'cf_record', return_value=record),
              patch.object(app, 'vpc_action', side_effect=vpc),
              patch.object(app, 'cf_request', side_effect=cf),
              patch.object(app, 'wait_eip', return_value={}),
              patch.object(app, 'prepare_node_nftables', side_effect=ValueError('SSH 不可达'))):
            result = app.rotate_one_eip(ACCOUNT)
        self.assertIn('换 IP 已成功', result)
        self.assertIn('nftables 未确认', result)
        self.assertEqual(calls[-1], 'ReleaseEipAddress')

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
