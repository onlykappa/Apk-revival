"""Real Qt widgets and worker jobs; Android launch boundary uses a test double."""
import pathlib,tempfile,unittest,time,os
from unittest.mock import patch,Mock
from test_pipeline import make_apk
from apk_revival.store import Store
try:
    from PySide6.QtWidgets import QApplication
    from apk_revival.launcher.ui import Window
except ImportError:QApplication=None  # The CI unit job installs no Qt.

@unittest.skipIf(QApplication is None,'PySide6 is not installed')
class OpenerUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name)
        self.check=patch.object(Window,'check_runtime');self.check.start()
        self.window=Window(Store(self.root/'private'));self.window.show();self.app.processEvents()
    def tearDown(self):
        self.wait();self.window.close();self.wait();self.app.processEvents();self.check.stop();self.temp.cleanup()
    def wait(self):
        end=time.monotonic()+8
        while self.window.worker and time.monotonic()<end:self.app.processEvents();time.sleep(.01)
        self.assertIsNone(self.window.worker)
    def test_file_open_imports_and_enables_play_without_prepare(self):
        self.window.open_apk(str(make_apk(self.root/'ordinary.apk',fixture=False)));self.wait()
        self.assertTrue(self.window.play_button.isVisible());self.assertTrue(self.window.play_button.isEnabled());self.assertFalse(self.window.prepare_button.isVisible());self.assertEqual(self.window.readiness_label.text(),'Ready to Play');self.assertEqual(len(self.window.cards),1)
    def test_multiple_dolphin_requests_queue_and_build_library(self):
        first=make_apk(self.root/'ordinary.apk',fixture=False);second=make_apk(self.root/'fixture.apk',fixture=True)
        self.window.open_apk(str(first));self.window.open_apk(str(second));self.wait()
        for _ in range(6):self.app.processEvents();time.sleep(.02);self.wait()
        self.assertEqual(len(self.window.cards),2)
    def test_play_button_runs_original_workflow_and_stop_returns_library(self):
        self.window.open_apk(str(make_apk(self.root/'ordinary.apk',fixture=False)));self.wait()
        runtime=Mock();self.window.service.runtime_factory=lambda serial:runtime;self.window.service.runtime_manager.ensure=Mock(return_value='fresh-ip:5555')
        self.window.play_button.click();self.wait();runtime.install.assert_called_once();self.assertTrue(runtime.install.call_args.kwargs['original']);runtime.launch.assert_called_once();self.assertTrue(self.window.stop_button.isVisible())
        self.window.stop_button.click();self.wait();self.assertIsNone(self.window.service.active);self.assertEqual(self.window.active_page,'library')

    def test_input_capture_button_runs_read_only_job(self):
        from PySide6.QtWidgets import QPushButton,QInputDialog
        from apk_revival.launcher.input_diagnostics import LABELS
        self.window.show_setup()
        selected=next(b for b in self.window.setup.findChildren(QPushButton) if b.text()=='Capture input diagnostics')
        with patch.object(QInputDialog,'getItem',return_value=(LABELS[0],True)),patch('apk_revival.launcher.input_diagnostics.collect',return_value={'directory':'/tmp/read-only-report','android_captured':False}) as capture:
            selected.click();self.wait();capture.assert_called_once()
        self.assertIn('host evidence only',self.window.message.text());self.assertIsNone(self.window.service.active)

    def test_library_request_runs_play_and_stop_through_normal_worker(self):
        self.window.open_apk(str(make_apk(self.root/'ordinary.apk',fixture=False)));self.wait()
        runtime=Mock();self.window.service.runtime_factory=lambda serial:runtime
        self.window.service.runtime_manager.ensure=Mock(return_value='current:5555')
        reply=Mock()
        self.assertTrue(self.window.run_library_request({'action':'play','game':self.window.current},reply))
        self.wait();runtime.launch.assert_called_once();self.assertEqual(reply.call_args.kwargs['state'],'succeeded')
        self.assertTrue(self.window.run_library_request({'action':'stop'},reply));self.wait()
        runtime.stop.assert_called_once();self.assertIsNone(self.window.service.active)

    def test_button_action_waits_for_status_check_instead_of_service_lock_error(self):
        monitor=Mock();monitor.isRunning.return_value=True;self.window.monitor_worker=monitor
        operation=Mock(return_value=None)
        self.window.submit('Stop game',operation)
        self.assertIsNone(self.window.worker);operation.assert_not_called()
        self.window.monitor_finished();self.app.processEvents();self.wait()
        operation.assert_called_once();self.assertIsNone(self.window.pending_submission)

    def test_mods_button_is_only_enabled_for_selected_running_meego(self):
        self.window.open_apk(str(make_apk(self.root/'ordinary.apk',fixture=False)));self.wait()
        self.assertFalse(self.window.mods_button.isVisible())
        p=self.window.profile();p['adapter']='meego-1.32';self.window.service.store.save(p);self.window.refresh()
        self.assertTrue(self.window.mods_button.isVisible());self.assertFalse(self.window.mods_button.isEnabled())
        self.window.service.active={'game':'different','kind':'android'};self.window.update_details()
        self.assertFalse(self.window.mods_button.isEnabled())
        self.window.service.active={'game':p['id'],'kind':'android'};self.window.update_details()
        self.assertTrue(self.window.mods_button.isEnabled())
        with patch('apk_revival.meego.mods_dialog.ModsDialog') as dialog:
            self.window.mods_button.click();dialog.assert_called_once_with(self.window.service,p['id'],self.window)
            dialog.return_value.exec.assert_called_once()
        self.window.service.active=None
