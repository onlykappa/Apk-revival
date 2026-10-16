import pathlib, signal, subprocess, tempfile, time, unittest
from unittest.mock import Mock, patch

from apk_revival.launcher.runtime_setup import RuntimeManager
from apk_revival.util import RevivalError


class StartupReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.manager=RuntimeManager()
        self.manager.startup_state_path=pathlib.Path(self.temp.name)/'startup'
        self.manager.bundle_process=Mock()
        self.manager.bundle_process.poll.return_value=None
        self.manager.bundle_started_at=0

    def tearDown(self):self.temp.cleanup()

    def test_authorization_must_finish_before_ready(self):
        self.manager.startup_state_path.write_text('authorizing\n')
        progress=Mock()
        def finish(_):self.manager.startup_state_path.write_text('ready\n')
        with patch('apk_revival.launcher.runtime_setup.time.monotonic',return_value=1),patch('apk_revival.launcher.runtime_setup.time.sleep',side_effect=finish):
            self.manager.wait_managed_startup(progress)
        progress.assert_called_once_with('Waiting for runtime setup authorization on the desktop')

    def test_guest_ready_does_not_hide_cancelled_authorization(self):
        self.manager.startup_state_path.write_text('failed\n')
        with patch('apk_revival.launcher.runtime_setup.time.monotonic',return_value=1):
            with self.assertRaisesRegex(RevivalError,'authorization was cancelled'):
                self.manager.wait_managed_startup()

    def test_ready_marker_requires_live_owned_helper(self):
        self.manager.startup_state_path.write_text('ready\n')
        self.manager.bundle_process.poll.return_value=1
        with patch('apk_revival.launcher.runtime_setup.time.monotonic',return_value=1):
            with self.assertRaisesRegex(RevivalError,'setup failed'):
                self.manager.wait_managed_startup()

    def test_expired_authorization_is_bounded(self):
        self.manager.startup_state_path.write_text('authorizing\n')
        with patch('apk_revival.launcher.runtime_setup.time.monotonic',return_value=111),patch('apk_revival.launcher.runtime_setup.time.sleep') as sleep:
            with self.assertRaisesRegex(RevivalError,'110 seconds'):
                self.manager.wait_managed_startup()
        sleep.assert_not_called()

    def test_shared_session_has_no_owned_authorization_gate(self):
        self.manager.bundle_process=None
        with patch('apk_revival.launcher.runtime_setup.time.sleep') as sleep:
            self.manager.wait_managed_startup()
        sleep.assert_not_called()

    def test_termination_releases_actual_owned_process_group(self):
        process=subprocess.Popen(['/bin/sleep','15'],start_new_session=True)
        self.manager.bundle_process=process
        try:
            self.manager.signal_owned_bundle(signal.SIGTERM)
            self.assertEqual(process.wait(timeout=3),-signal.SIGTERM)
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=3)

