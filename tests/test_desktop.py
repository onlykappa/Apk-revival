"""Opt-in actual Tk interface smoke tests, requiring an X display."""
import os,pathlib,tempfile,time,unittest
from unittest.mock import patch
from apk_revival.store import Store
from apk_revival.analysis import analyze
from apk_revival.backend import Progress
from test_pipeline import make_apk

@unittest.skipUnless(os.getenv('APKR_UI_TEST'),'Set APKR_UI_TEST=1 with a working DISPLAY to exercise actual Tk windows')
class DesktopTests(unittest.TestCase):
    def test_library_report_plan_and_restore_progress(self):
        from apk_revival.ui import App
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);s=Store(root/'private');p=s.import_game(make_apk(root/'test.apk'));analyze(s,p['id']);app=App(s)
            try:
                app.refresh(p['id']);app.root.update();self.assertIn(p['id'],app.tree.get_children());self.assertIn('APK SHA-256',app.report.get('1.0','end'));app.plan()
                deadline=time.monotonic()+5
                while app.busy and time.monotonic()<deadline:app.root.update();time.sleep(.02)
                self.assertFalse(app.busy);self.assertIn('expected_sha256',app.plan_view.get('1.0','end'));self.assertIn('SELF-AUTHORED FIXTURE',app.subtitle.cget('text'))
            finally:app.close()
    def test_rebuild_actual_coin_button_persists_on_relaunch(self):
        import tkinter as tk
        from apk_revival.rebuild_game import run
        with tempfile.TemporaryDirectory() as temp:
            save=pathlib.Path(temp)/'progress.json';real_tk=tk.Tk
            for iteration in range(2):
                def make_window():
                    window=real_tk()
                    def exercise():
                        button=next(w for w in window.winfo_children() if isinstance(w,tk.Button));button.invoke();window.destroy()
                    window.after(150,exercise);return window
                with patch('tkinter.Tk',side_effect=make_window):run(save)
                self.assertEqual(Progress(save).get()['coins'],iteration+1)
