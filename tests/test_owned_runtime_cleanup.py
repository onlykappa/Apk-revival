import subprocess,tempfile,unittest
from unittest.mock import Mock,patch
from apk_revival.launcher.runtime_setup import RuntimeManager
from apk_revival.util import RevivalError

class OwnedRuntimeCleanupTests(unittest.TestCase):
    def test_graceful_android_stop_precedes_owned_compositor_termination(self):
        manager=RuntimeManager();process=Mock();process.poll.return_value=None
        process.wait.side_effect=[subprocess.TimeoutExpired('cage',5),None]
        manager.bundle_process=process;manager.bundle_log=tempfile.TemporaryFile()
        order=[]
        process.terminate.side_effect=lambda:order.append('terminate')
        with patch('apk_revival.launcher.runtime_setup.tool',return_value='waydroid'),patch('apk_revival.launcher.runtime_setup.command',side_effect=lambda *a,**kw:order.append('session stop')):
            manager.stop_owned_session()
        self.assertEqual(order,['session stop','terminate']);self.assertIsNone(manager.bundle_process)
        self.assertIsNone(manager.bundle_log);process.kill.assert_not_called()

    def test_shared_runtime_is_never_stopped(self):
        manager=RuntimeManager()
        with patch('apk_revival.launcher.runtime_setup.command') as command:
            manager.stop_owned_session()
        command.assert_not_called()

    def test_failed_session_stop_keeps_compositor_instead_of_breaking_connection(self):
        manager=RuntimeManager();process=Mock();process.poll.return_value=None;manager.bundle_process=process
        with patch('apk_revival.launcher.runtime_setup.tool',return_value='waydroid'),patch('apk_revival.launcher.runtime_setup.command',side_effect=RevivalError('stop failed')):
            with self.assertRaisesRegex(RevivalError,'stop failed'):manager.stop_owned_session()
        self.assertIs(manager.bundle_process,process);process.terminate.assert_not_called();process.kill.assert_not_called()
