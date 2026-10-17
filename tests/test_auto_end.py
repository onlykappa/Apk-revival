"""A closed game ends its session without pressing Stop, even while Android keeps its process cached."""
import os, pathlib, tempfile, time, unittest
from unittest.mock import Mock
from apk_revival.launcher.service import Launcher, OFFSCREEN_LIMIT
from apk_revival.store import Store
from apk_revival.util import RevivalError

GAME = 'example.game'
OLD_FORMAT = '  mResumedActivity: ActivityRecord{1a2b u0 %s t12}\n'          # Android 10-11
NEW_FORMAT = '  topResumedActivity=ActivityRecord{1a2b u0 %s t12}\n    ResumedActivity: ActivityRecord{1a2b u0 %s t12}\n'  # 12+


class AutoEndTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.launcher = Launcher(Store(pathlib.Path(self.temp.name)))
        self.launcher.runtime_manager.stop_owned_session = Mock()
        self.runtime = Mock(); self.runtime.backend = None; self.runtime.package = GAME
        self.pid, self.screen = '4321', OLD_FORMAT % (GAME + '/.Main')
        def shell(*args, timeout=60):
            if args[0] == 'pidof':return self.pid
            if args[:2] == ('dumpsys', 'activity'):
                if isinstance(self.screen, Exception):raise self.screen
                return self.screen
            return ''
        self.runtime.shell.side_effect = shell
        self.launcher.android = self.runtime
        self.launcher.active = {'kind': 'android', 'game': 'a' * 24, 'serial': 'guest:5555'}

    def test_closed_game_with_cached_process_ends_after_grace_period(self):
        self.screen = OLD_FORMAT % 'com.android.launcher3/.Launcher'
        for _ in range(OFFSCREEN_LIMIT - 1):
            self.assertIsNone(self.launcher.monitor());self.runtime.stop.assert_not_called()
        self.assertEqual(self.launcher.monitor(), 'The game has closed.')
        self.runtime.stop.assert_called_once();self.assertIsNone(self.launcher.active)

    def test_brief_dialog_from_another_app_does_not_end_the_game(self):
        self.screen = NEW_FORMAT % (('com.google.android.gms/.SignIn',) * 2)
        self.launcher.monitor()
        self.screen = NEW_FORMAT % ((GAME + '/.Main',) * 2)
        for _ in range(OFFSCREEN_LIMIT + 1):self.assertIsNone(self.launcher.monitor())
        self.runtime.stop.assert_not_called();self.assertEqual(self.launcher.offscreen_checks, 0)

    def test_unknown_output_or_failed_query_never_ends_a_running_game(self):
        for screen in ('Permission Denial: can\'t dump activity manager', RevivalError('dumpsys timed out')):
            self.screen = screen
            for _ in range(OFFSCREEN_LIMIT + 1):self.assertIsNone(self.launcher.monitor())
        self.runtime.stop.assert_not_called()

    def test_similar_package_name_is_not_mistaken_for_the_game(self):
        self.screen = OLD_FORMAT % (GAME + '.helper/.Main')
        for _ in range(OFFSCREEN_LIMIT):self.launcher.monitor()
        self.runtime.stop.assert_called_once()

    def test_exited_process_still_ends_immediately(self):
        self.pid = ''
        self.assertEqual(self.launcher.monitor(), 'The game has closed.');self.runtime.stop.assert_called_once()


@unittest.skipUnless(os.getenv('QT_QPA_PLATFORM') == 'offscreen', 'Qt offscreen test')
class SteamSessionCloseTests(unittest.TestCase):
    def window(self, close_after_game):
        from PySide6.QtWidgets import QApplication
        from apk_revival.launcher.ui import Window
        self.app = QApplication.instance() or QApplication([])
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        w = Window(Store(pathlib.Path(temp.name)), close_after_game=close_after_game)
        w.service.runtime_manager.discover = lambda *a, **k: {'ready': False, 'devices': [], 'waydroid': False, 'steam_os': False, 'errors': []}
        w.show(); self.addCleanup(w.close); return w

    def settle(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:self.app.processEvents();time.sleep(.02)

    def test_steam_game_shortcut_closes_the_app_when_the_game_ends(self):
        w = self.window(True);w.game_ended();self.settle(.3)
        self.assertTrue(w.isVisible(), 'never close before a game actually ran')
        w.game_started = True;w.monitored('The game has closed.');self.settle(2.2)
        self.assertFalse(w.isVisible())

    def test_library_opened_normally_stays_open(self):
        w = self.window(False);w.game_started = True;w.monitored('The game has closed.');self.settle(2.2)
        self.assertTrue(w.isVisible())


if __name__ == '__main__':
    unittest.main()
