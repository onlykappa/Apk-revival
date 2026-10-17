"""Controller-to-touch mapping: stored points, screen size, taps and the controller hook."""
import os, pathlib, tempfile, unittest
from unittest.mock import patch
from apk_revival import touch_mapping
from apk_revival.store import Store
from apk_revival.util import RevivalError


class FakeProcess:
    def __init__(self, *args, **kwargs):
        self.args, self.lines, self.alive = args[0], [], True
        self.stdin = self
    def write(self, text):self.lines.append(text)
    def flush(self):pass
    def poll(self):return None if self.alive else 0
    def wait(self, timeout=None):self.alive = False
    def kill(self):self.alive = False


class Screen:
    serial = 'emulator-5554'
    def __init__(self, output='Physical size: 1280x800\n'):self.output = output
    def shell(self, *args, timeout=60):return self.output if args in (('wm', 'size'), ('dumpsys', 'window', 'displays')) else ''


class Ctx:
    def __init__(self):self.steps = []
    def step(self, text):self.steps.append(text)


class MappingTests(unittest.TestCase):
    def test_stored_points_are_validated_and_round_trip(self):
        p = {'launcher': {'controls': {'0': [0.5, 0.25], '5': [0.1, 0.1], '1': [2, 0.5], 'x': [0, 0], '9': 'bad'}}}
        self.assertEqual(touch_mapping.mapping(p), {0: (0.5, 0.25)})
        self.assertEqual(touch_mapping.mapping({}), {})
        self.assertEqual(touch_mapping.store_format({0: (0.123456, 1.0), 5: (0, 0)}), {'0': [0.1235, 1.0]})
        self.assertEqual(touch_mapping.mapping({'launcher': {'controls': touch_mapping.store_format({14: (0.9, 0.1)})}}), {14: (0.9, 0.1)})

    def test_screen_size_prefers_override_and_pixels_stay_on_screen(self):
        self.assertEqual(touch_mapping.screen_size(Screen()), (1280, 800))
        self.assertEqual(touch_mapping.screen_size(Screen('Physical size: 1280x800\nOverride size: 800x1280\n')), (800, 1280))
        with self.assertRaises(RevivalError):touch_mapping.screen_size(Screen('error'))
        self.assertEqual(touch_mapping.screen_size(Screen('  mDisplayInfo cur=800x1280 app=800x1232\nPhysical size: 1280x800\n')), (800, 1280), 'rotation is followed')
        self.assertEqual(touch_mapping.pixel((0, 0), (1280, 800)), (0, 0))
        self.assertEqual(touch_mapping.pixel((1, 1), (1280, 800)), (1279, 799))

    def test_tap_sender_writes_to_one_shell(self):
        with patch('apk_revival.touch_mapping.tool', return_value='adb'):
            sender = touch_mapping.TapSender('emulator-5554', popen=FakeProcess)
        self.assertEqual(sender.process.args, ['adb', '-s', 'emulator-5554', 'shell'])
        self.assertTrue(sender.tap(10, 20));self.assertTrue(sender.tap(30.7, 40))
        self.assertEqual(sender.process.lines, ['input tap 10 20\n', 'input tap 30 40\n'])
        sender.close();self.assertEqual(sender.process.lines[-1], 'exit\n');self.assertFalse(sender.tap(1, 1))
        with self.assertRaises(RevivalError):touch_mapping.TapSender(None, popen=FakeProcess)


class ServiceTouchTests(unittest.TestCase):
    def setUp(self):
        from apk_revival.launcher.service import Launcher
        self.temp = tempfile.TemporaryDirectory();self.service = Launcher(Store(pathlib.Path(self.temp.name)))
        self.p = {'launcher': {'controls': {'0': [0.5, 0.5], '11': [0, 0]}}}
        self.patches = [patch('apk_revival.touch_mapping.subprocess.Popen', FakeProcess), patch('apk_revival.touch_mapping.tool', return_value='adb')]
        for item in self.patches:item.start()
    def tearDown(self):
        for item in self.patches:item.stop()
        self.temp.cleanup()

    def test_presses_become_taps_and_stop_closes_the_shell(self):
        self.service.start_touch(self.p, Screen(), Ctx())
        process = self.service.touch['sender'].process
        self.assertTrue(self.service.touch_press(0));self.assertTrue(self.service.touch_press(11));self.assertFalse(self.service.touch_press(2))
        self.assertEqual(process.lines, ['input tap 640 400\n', 'input tap 0 0\n'])
        self.service.release_game_settings()
        self.assertIsNone(self.service.touch);self.assertFalse(process.alive);self.assertFalse(self.service.touch_press(0))

    def test_unmapped_game_and_failures_never_block_play(self):
        ctx = Ctx();self.service.start_touch({'launcher': {}}, Screen(), ctx)
        self.assertIsNone(self.service.touch);self.assertEqual(ctx.steps, [])
        ctx = Ctx();self.service.start_touch(self.p, Screen('broken'), ctx)
        self.assertIsNone(self.service.touch);self.assertTrue(ctx.steps[-1].startswith('Controller taps are off'))

    def test_screenshot_needs_a_running_game(self):
        with self.assertRaisesRegex(RevivalError, 'Start the game first'):self.service.screenshot()


class ControllerHookTests(unittest.TestCase):
    def test_presses_are_forwarded_only_while_the_game_has_focus(self):
        try:
            os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
            from PySide6.QtWidgets import QApplication, QWidget
            from apk_revival.launcher import controller
        except ImportError:self.skipTest('PySide6 is not installed')
        app = QApplication.instance() or QApplication([])
        state = {}
        class Lib:
            def SDL_GameControllerUpdate(self):pass
            def SDL_GameControllerGetAttached(self, h):return 1
            def SDL_NumJoysticks(self):return 1
            def SDL_IsGameController(self, i):return 1
            def SDL_GameControllerName(self, h):return b'Pad'
            def SDL_GameControllerGetButton(self, h, n):return int(state.get(n, False))
            def SDL_GameControllerGetAxis(self, h, n):return 0
        window = QWidget()
        pad = controller.Controller.__new__(controller.Controller)
        pad.window, pad.back, pad.options = window, lambda: None, lambda: None
        pad.lib, pad.handles, pad.previous, pad.last_dir, pad.repeat, pad.connected = Lib(), {0: 1}, {}, None, 0, []
        sent = [];pad.game_buttons = sent.append
        state[9] = True;pad.poll();pad.poll()
        self.assertEqual(sent, [9], 'one tap per press, not per poll')
        state[9] = False;pad.poll();state[9] = True
        with patch.object(window, 'isActiveWindow', return_value=True):pad.poll()
        self.assertEqual(sent, [9], 'nothing is sent while APK Revival itself has focus')
        window.deleteLater()


if __name__ == '__main__':
    unittest.main()
