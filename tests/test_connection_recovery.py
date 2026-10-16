"""Connection recovery against mocks only; no live Android or local services."""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from apk_revival.launcher.connection_recovery import recover
from apk_revival.runtime import WaydroidRuntime
from apk_revival.util import RevivalError


class ConnectionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.info = {'waydroid': True, 'session': 'RUNNING', 'container': 'RUNNING',
                     'ready': True, 'ip': '192.168.240.112',
                     'devices': [{'serial': '192.168.240.112:5555', 'state': 'device'},
                                 {'serial': 'unrelated-phone', 'state': 'device'}]}
        self.manager = SimpleNamespace(discover=Mock(side_effect=lambda **_: copy.deepcopy(self.info)))
        self.runtime = WaydroidRuntime('192.168.240.100:5555')
        self.runtime.package = 'ata.apkrv.meego'
        self.backend = SimpleNamespace(port=8770, token='a' * 32,
                                       thread=SimpleNamespace(is_alive=Mock(return_value=True)),
                                       progress={'saved_village': 'preserve'}, stop=Mock())
        self.runtime.backend = self.backend
        self.runtime.forward_port = 8770
        self.runtime.shell = Mock(return_value='1234')
        self.runtime.adb = Mock(return_value=self.health())
        for name in ('install', 'launch', 'start_backend', 'stop_backend', 'stop'):
            setattr(self.runtime, name, Mock())
        self.active = {'game': 'b' * 24, 'serial': self.runtime.serial, 'kind': 'android'}

    def health(self, token=None, **extra):
        body = {'token': self.backend.token if token is None else token}
        body.update(extra)
        return 'HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n' + json.dumps(body)

    def check_preserved(self):
        self.assertIs(self.runtime.backend, self.backend)
        self.assertEqual(self.backend.progress, {'saved_village': 'preserve'})
        self.backend.stop.assert_not_called()
        for name in ('install', 'launch', 'start_backend', 'stop_backend', 'stop'):
            getattr(self.runtime, name).assert_not_called()
        self.manager.discover.assert_called_once_with(connect=True, probe_timeout=3)

    def test_reconnects_only_current_managed_guest_and_keeps_healthy_reverse(self):
        result = recover(self.manager, self.runtime, self.active)
        self.assertEqual(result['state'], 'recovered')
        self.assertEqual(self.runtime.serial, '192.168.240.112:5555')
        self.assertEqual(self.active['serial'], self.runtime.serial)
        self.runtime.shell.assert_called_once_with('pidof', 'ata.apkrv.meego', timeout=3)
        self.assertEqual(self.runtime.adb.call_count, 1)
        self.assertEqual(self.runtime.adb.call_args.args[:2], ('shell', '-T'))
        self.assertEqual(self.runtime.adb.call_args.kwargs['timeout'], 5)
        self.check_preserved()

    def test_missing_reverse_rebinds_owned_port_once_then_checks_same_service(self):
        self.runtime.adb.side_effect = [RevivalError('No response'), '', self.health()]
        self.assertEqual(recover(self.manager, self.runtime, self.active)['state'], 'recovered')
        self.assertEqual(self.runtime.adb.call_count, 3)
        reverse = self.runtime.adb.call_args_list[1]
        self.assertEqual(reverse.args, ('reverse', 'tcp:8770', 'tcp:8770'))
        self.assertEqual(reverse.kwargs, {'timeout': 3})
        self.assertEqual(self.runtime.adb.call_args_list[0].kwargs['timeout'], 5)
        self.assertEqual(self.runtime.adb.call_args_list[2].kwargs['timeout'], 5)
        self.assertEqual(self.runtime.forward_port, 8770)
        self.check_preserved()

    def test_conflicting_nonce_does_not_claim_recovery_or_replace_backend(self):
        self.runtime.adb.side_effect = [self.health('c' * 32), '', self.health('c' * 32)]
        result = recover(self.manager, self.runtime, self.active)
        self.assertEqual(result['state'], 'failed')
        self.assertEqual(self.runtime.adb.call_count, 3)
        self.check_preserved()

    def test_nonce_occurrence_in_unrelated_field_is_not_health_identity(self):
        wrong = self.health('c' * 32, unrelated=self.backend.token)
        self.runtime.adb.side_effect = [wrong, '', wrong]
        result = recover(self.manager, self.runtime, self.active)
        self.assertEqual(result['state'], 'failed')
        self.assertIn('different service', result['detail'])
        self.check_preserved()

    def test_frozen_guest_is_paused_without_pid_probe_reverse_or_cleanup(self):
        self.info.update(container='FROZEN', ready=False)
        before = copy.deepcopy(self.active)
        self.assertEqual(recover(self.manager, self.runtime, self.active)['state'], 'paused')
        self.assertEqual(self.active, before)
        self.runtime.shell.assert_not_called()
        self.runtime.adb.assert_not_called()
        self.check_preserved()

    def test_stopped_runtime_does_not_start_anything_or_mutate_serial(self):
        self.info.update(session='STOPPED', container='STOPPED', ready=False)
        before = copy.deepcopy(self.active)
        self.assertEqual(recover(self.manager, self.runtime, self.active)['state'], 'failed')
        self.assertEqual(self.active, before)
        self.assertEqual(self.runtime.serial, before['serial'])
        self.runtime.shell.assert_not_called()
        self.runtime.adb.assert_not_called()
        self.check_preserved()

    def test_other_connected_devices_and_offline_managed_guest_are_ignored(self):
        self.info['devices'][0]['state'] = 'offline'
        before = copy.deepcopy(self.active)
        self.assertEqual(recover(self.manager, self.runtime, self.active)['state'], 'failed')
        self.assertEqual(self.active, before)
        self.assertEqual(self.runtime.serial, before['serial'])
        self.runtime.shell.assert_not_called()
        self.runtime.adb.assert_not_called()
        self.check_preserved()

    def test_missing_verified_ip_never_falls_back_to_any_adb_device(self):
        self.info['ip'] = None
        before = copy.deepcopy(self.active)
        self.assertEqual(recover(self.manager, self.runtime, self.active)['state'], 'failed')
        self.assertEqual(self.active, before)
        self.runtime.adb.assert_not_called()
        self.check_preserved()

    def test_exited_game_or_failed_pid_check_preserves_service_for_caller_policy(self):
        for response in ('', RevivalError('Disconnected again')):
            with self.subTest(response=str(response)):
                self.manager.discover.reset_mock()
                self.runtime.shell.reset_mock()
                self.runtime.shell.side_effect = response if isinstance(response, Exception) else None
                self.runtime.shell.return_value = response
                self.assertEqual(recover(self.manager, self.runtime, self.active)['state'], 'failed')
                self.runtime.adb.assert_not_called()
                self.check_preserved()

    def test_unowned_reverse_or_dead_backend_is_not_rebound(self):
        self.runtime.forward_port = 9999
        self.assertEqual(recover(self.manager, self.runtime, self.active)['state'], 'failed')
        self.runtime.adb.assert_not_called()
        self.check_preserved()
        self.manager.discover.reset_mock()
        self.runtime.forward_port = 8770
        self.backend.thread.is_alive.return_value = False
        self.assertEqual(recover(self.manager, self.runtime, self.active)['state'], 'failed')
        self.runtime.adb.assert_not_called()
        self.check_preserved()

    def test_original_apk_without_backend_recovers_existing_game_only(self):
        self.runtime.backend = None
        self.runtime.forward_port = None
        self.assertEqual(recover(self.manager, self.runtime, self.active)['state'], 'recovered')
        self.runtime.adb.assert_not_called()
        for name in ('install', 'launch', 'start_backend', 'stop_backend', 'stop'):
            getattr(self.runtime, name).assert_not_called()

    def test_discovery_timeout_is_one_failure_without_runtime_mutation(self):
        self.manager.discover.side_effect = RevivalError('Discovery timed out')
        before = copy.deepcopy(self.active)
        result = recover(self.manager, self.runtime, self.active)
        self.assertEqual(result['state'], 'failed')
        self.assertIn('timed out', result['detail'])
        self.assertEqual(self.active, before)
        self.runtime.adb.assert_not_called()
        self.check_preserved()

    def test_failed_managed_display_check_preserves_runtime_without_restart(self):
        self.manager.check_managed_display = Mock(return_value=False)
        result = recover(self.manager, self.runtime, self.active)
        self.assertEqual(result['state'], 'failed')
        self.assertIn('display', result['detail'])
        self.manager.check_managed_display.assert_called_once_with(self.info)
        self.runtime.shell.assert_not_called()
        self.runtime.adb.assert_not_called()
        self.check_preserved()

    def test_unknown_or_healthy_display_check_allows_owned_connection_checks(self):
        for state in (None, True):
            with self.subTest(display_state=state):
                self.manager.discover.reset_mock()
                self.manager.check_managed_display = Mock(return_value=state)
                self.assertEqual(recover(self.manager, self.runtime, self.active)['state'], 'recovered')
                self.manager.check_managed_display.assert_called_once_with(self.info)
                self.check_preserved()


if __name__ == '__main__':
    unittest.main()
