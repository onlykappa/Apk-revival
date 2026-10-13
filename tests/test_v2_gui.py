"""Real Qt workflow tests. Android discovery is a test double; V1 tools are real."""
import os,pathlib,tempfile,time,unittest,zipfile
from unittest.mock import patch

try:
 from PySide6.QtCore import QTimer,Qt
 from PySide6.QtWidgets import QApplication,QDialog,QComboBox,QPushButton,QFileDialog
 from PySide6.QtTest import QTest
 HAS_QT=True
except ImportError:HAS_QT=False

@unittest.skipUnless(HAS_QT and os.getenv('APKR_V2_UI_TEST'),'Enable APKR_V2_UI_TEST with Qt and the real fixture/tools available')
class V2GUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from apk_revival.launcher.style import STYLE
        cls.app=QApplication.instance() or QApplication([]);cls.app.setStyle('Fusion');cls.app.setStyleSheet(STYLE)
    def setUp(self):
        from apk_revival.launcher.ui import Window
        from apk_revival.store import Store
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.w=Window(Store(self.root/'private'));self.w.service.runtime_manager.discover=lambda *a,**k:{'ready':False,'devices':[],'waydroid':False,'steam_os':False};self.w.show();self.w.activateWindow();self.app.processEvents();QTest.qWait(120);self.wait()
    def tearDown(self):self.wait();self.w.close();self.app.processEvents();self.temp.cleanup()
    def wait(self,timeout=20):
        end=time.monotonic()+timeout
        while self.w.worker and time.monotonic()<end:self.app.processEvents();QTest.qWait(20)
        self.assertIsNone(self.w.worker,'GUI job did not finish')
    def click_modal(self,text,extra=None):
        def click():
            d=self.app.activeModalWidget();self.assertIsNotNone(d)
            if extra:extra(d)
            next(b for b in d.findChildren(QPushButton) if b.text()==text).click()
        QTimer.singleShot(60,click)
    def import_ui(self):
        apk=os.environ.get('APKR_TEST_APK',str(pathlib.Path(__file__).resolve().parents[1]/'resources/tapquest-original.apk'))
        def fill():
            d=self.app.activeModalWidget();d.apk.setText(apk);d.add.click()
        QTimer.singleShot(50,fill);self.w.add_button.click();self.wait();self.assertEqual(len(self.w.cards),1);self.assertEqual(self.w.profile()['title'],'Tap Quest')
        return self.w.current
    def test_complete_add_prepare_play_save_restore_export_interface(self):
        game=self.import_ui();self.w.prepare_button.click();self.wait();p=self.w.profile();self.assertTrue(p['restoration']['signature_verified']);self.assertEqual(self.w.readiness_label.text(),'Prepared');self.assertTrue(self.w.play_button.isVisible());self.assertFalse(self.w.prepare_button.isVisible());self.assertTrue(self.w.play_button.isEnabled());self.assertNotEqual(p['status'],'Verified Offline')
        self.click_modal('Save options',lambda d:d.findChild(QComboBox).setCurrentIndex(2));self.w.options_button.click();self.assertTrue(self.w.prepare_button.isVisible());self.assertFalse(self.w.play_button.isVisible());self.w.prepare_button.click();self.wait();self.assertEqual(self.w.readiness_label.text(),'Separate rebuild ready');self.assertTrue(self.w.play_button.isVisible());self.assertFalse(self.w.prepare_button.isVisible())
        self.w.play_button.click();self.wait();self.assertEqual(self.w.active_page,'game');QTest.mouseClick(self.w.rebuild_view.collect,Qt.MouseButton.LeftButton);self.assertEqual(self.w.rebuild_view.progress.get()['coins'],1)
        self.w.controller.dispatch('back');self.wait();self.assertEqual(self.w.active_page,'library');self.w.play_button.click();self.wait();self.assertEqual(self.w.rebuild_view.progress.get()['coins'],1);self.w.stop();self.wait()
        self.click_modal('Backup save');self.w.options_button.click();self.wait();backups=list((self.w.service.store.directory(game)/'backups').glob('*.zip'));self.assertEqual(len(backups),1)
        self.w.play_button.click();self.wait();self.w.rebuild_view.collect.click();self.w.stop();self.wait()
        self.click_modal('Restore save')
        with patch.object(QFileDialog,'getOpenFileName',return_value=(str(backups[0]),'ZIP')):self.w.options_button.click()
        self.wait();self.w.play_button.click();self.wait();self.assertEqual(self.w.rebuild_view.progress.get()['coins'],1);self.w.stop();self.wait()
        out=self.root/'export.zip';self.click_modal('Export game')
        with patch.object(QFileDialog,'getSaveFileName',return_value=(str(out),'ZIP')):self.w.options_button.click()
        self.wait();self.assertTrue(out.exists())
        with zipfile.ZipFile(out) as z:self.assertIn('run.py',z.namelist());self.assertFalse(any('/saves/' in n for n in z.namelist()))
    def test_focus_navigation_and_controller_action(self):
        self.import_ui();self.w.show();self.w.activateWindow();self.app.processEvents();self.w.prepare_button.setFocus();self.w.controller.dispatch('right');self.assertIsNot(self.app.focusWidget(),self.w.prepare_button)
        self.w.demo_button.setFocus();self.w.controller.dispatch('confirm');self.wait();self.assertEqual(self.w.profile()['restoration']['path'],'rebuild')
        self.w.play_button.setFocus();self.w.controller.dispatch('confirm');self.wait();self.w.rebuild_view.collect.setFocus();self.w.controller.dispatch('confirm');self.assertEqual(self.w.rebuild_view.progress.get()['coins'],1);self.w.controller.dispatch('back');self.wait()
    def test_fixture_demo_no_android_and_unsupported_drop(self):
        self.w.demo_button.click();self.wait();self.assertEqual(self.w.profile()['restoration']['path'],'rebuild');self.assertTrue(self.w.play_button.isEnabled());self.assertNotEqual(self.w.profile()['status'],'Verified Offline')

if __name__=='__main__':unittest.main()
