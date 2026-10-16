import pathlib,tempfile,unittest
from unittest.mock import Mock,patch
from apk_revival.launcher.service import Launcher
from apk_revival.store import Store
from apk_revival.util import RevivalError

class MonitorRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.launcher=Launcher(Store(pathlib.Path(self.temp.name)))
        self.runtime=Mock();self.runtime.backend=None;self.runtime.package='example.game'
        self.runtime.shell.side_effect=RevivalError('transport disconnected')
        self.launcher.android=self.runtime;self.launcher.active={'kind':'android','game':'a'*24,'serial':'old:5555'}

    def test_transient_disconnect_keeps_game_and_backend_and_success_resets_count(self):
        with patch('apk_revival.launcher.connection_recovery.recover',side_effect=[{'state':'failed','detail':'temporary'}, {'state':'recovered','detail':'ok'}]):
            self.assertIn('1/3',self.launcher.monitor());self.runtime.stop.assert_not_called()
            self.assertIs(self.launcher.android,self.runtime)
            self.assertIn('Reconnected',self.launcher.monitor());self.assertEqual(self.launcher.connection_failures,0)

    def test_three_failed_checks_end_owned_session_with_useful_error(self):
        with patch('apk_revival.launcher.connection_recovery.recover',return_value={'state':'failed','detail':'no current guest'}):
            self.launcher.monitor();self.launcher.monitor();self.runtime.stop.assert_not_called()
            self.assertIn('three checks',self.launcher.monitor())
        self.runtime.stop.assert_called_once();self.assertIsNone(self.launcher.active)

    def test_suspended_runtime_is_retained_without_spurious_shutdown(self):
        with patch('apk_revival.launcher.connection_recovery.recover',return_value={'state':'paused','detail':'runtime suspended'}):
            self.assertIn('suspended',self.launcher.monitor())
        self.runtime.stop.assert_not_called();self.assertIs(self.launcher.android,self.runtime)
