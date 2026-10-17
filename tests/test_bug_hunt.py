"""Regressions found in the 0.9.2 bug hunt: runtime startup, network cleanup, saves, import and controller."""
import os, pathlib, socket, sys, tempfile, threading, time, unittest, zipfile
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_pipeline import make_apk
from test_reviver_essentials import PACKAGE, bundle
from apk_revival import android_saves, game_network
from apk_revival.store import Store
from apk_revival.util import RevivalError


class Alive:
    def poll(self):return None


class Quiet:
    def step(self, *a):pass


def launcher(root):
    from apk_revival.launcher.service import Launcher
    return Launcher(Store(pathlib.Path(root)))


class RuntimeStartupTests(unittest.TestCase):
    def test_runtime_started_long_ago_is_ready_not_late(self):
        from apk_revival.launcher.runtime_setup import RuntimeManager
        with tempfile.TemporaryDirectory() as temp:
            manager = RuntimeManager(pathlib.Path(temp) / 'state.json')
            manager.startup_state_path = pathlib.Path(temp) / 'startup';manager.startup_state_path.write_text('ready')
            manager.bundle_process, manager.bundle_started_at = Alive(), time.monotonic() - 600
            manager.wait_managed_startup()  # Used to raise "did not finish within 110 seconds".
            manager.startup_state_path.write_text('authorizing')
            with self.assertRaisesRegex(RevivalError, '110 seconds'):manager.wait_managed_startup()


class Android:
    """Records commands; can pretend the connection is gone."""
    serial = 'emulator-5554'
    def __init__(self):self.commands, self.offline = [], False
    def shell(self, *args, timeout=60):
        if self.offline:raise RevivalError('device offline')
        self.commands.append(args)
        if args[:4] == ('cmd', 'package', 'list', 'packages'):return f'package:{PACKAGE} uid:10057\n'
        return ''
    def adb(self, *args, timeout=60):
        if self.offline:raise RevivalError('device offline')
        self.commands.append(('adb',) + args);return ''


class NetworkCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.service = launcher(self.temp.name)
        self.p = {'id': 'a' * 24, 'analysis': {'metadata': {'package': PACKAGE}}, 'launcher': {'network': 'log'}}
    def tearDown(self):
        self.service.stop_network();self.temp.cleanup()

    def test_unreachable_android_keeps_the_proxy_marked_for_cleanup(self):
        android = Android();self.service.start_network(self.p, android, Quiet())
        android.offline = True;self.service.stop_network()
        self.assertTrue(self.service.settings['network_applied'], 'the next Play must still reset the proxy')
        self.assertFalse(game_network.clear_proxy(android))

    def test_reconnect_restores_the_proxy_reverse_rule_and_tap_shell(self):
        android = Android();self.service.start_network(self.p, android, Quiet());self.service.android = android
        port = self.service.network['proxy'].port
        closed = []
        class Sender:
            def __init__(self, serial):self.serial = serial
            def close(self):closed.append(self)
        self.service.touch = {'points': {0: (0.5, 0.5)}, 'size': (1280, 800), 'sender': Sender('old')}
        android.commands.clear()
        with patch('apk_revival.touch_mapping.TapSender', Sender):self.service.reconnected()
        self.assertIn(('adb', 'reverse', f'tcp:{port}', f'tcp:{port}'), android.commands)
        self.assertEqual(len(closed), 1);self.assertEqual(self.service.touch['sender'].serial, 'emulator-5554')


class JobLogTests(unittest.TestCase):
    def test_background_checks_leave_no_history_and_old_logs_are_pruned(self):
        from apk_revival.launcher.jobs import Jobs
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            jobs = Jobs(folder)
            jobs.run('Check running game', lambda ctx: None, record=False)
            self.assertEqual(jobs.history, []);self.assertEqual(list(folder.glob('*.json')), [])
            jobs.run('Play', lambda ctx: None);self.assertEqual(len(list(folder.glob('*.json'))), 1)
            for i in range(250):(folder / f'{i:04d}.json').write_text('{}')
            Jobs(folder);self.assertEqual(len(list(folder.glob('*.json'))), 200)


class PlaytimeTests(unittest.TestCase):
    def test_sleep_is_not_counted(self):
        with tempfile.TemporaryDirectory() as temp:
            service = launcher(temp)
            p = service.store.import_game(make_apk(pathlib.Path(temp) / 'g.apk', fixture=False))
            # Wall clock says ten hours (the Deck slept); the monotonic clock says two minutes.
            service.active = {'game': p['id'], 'started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - 36000)), 'clock': time.monotonic() - 120}
            service.record_playtime()
            self.assertTrue(115 <= service.store.load(p['id'])['launcher']['playtime_seconds'] <= 130)


class SaveBackupTests(unittest.TestCase):
    def test_failed_backup_leaves_no_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            target = pathlib.Path(temp) / 'backups' / 'b.zip'
            def broken(runtime, p, package, path):
                pathlib.Path(path).write_bytes(b'PK partial');raise RevivalError('adb pull timed out')
            with patch.object(android_saves, '_require'), patch.object(android_saves, '_write_backup', broken):
                with self.assertRaises(RevivalError):android_saves.backup(Android(), {'analysis': {'metadata': {'package': PACKAGE}}}, target)
            self.assertEqual(list(target.parent.iterdir()), [])

    def test_large_backup_parts_are_restorable(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / 'b.zip'
            with zipfile.ZipFile(path, 'w') as z:z.writestr('backup.json', '{}')
            with patch.object(android_saves, 'inspect_zip', side_effect=RevivalError('stop here')) as inspected:
                with self.assertRaises(RevivalError):android_saves.restore(Android(), {'analysis': {'metadata': {'package': PACKAGE}}}, path)
            self.assertGreaterEqual(inspected.call_args.kwargs['max_member'], 8 * 1024**3)


class ProxyTests(unittest.TestCase):
    def test_log_is_trimmed_and_loopback_is_relayed_offline_and_tunnels_close(self):
        from apk_revival.netproxy import MAX_LOG_LINES, Proxy
        with tempfile.TemporaryDirectory() as temp:
            log = pathlib.Path(temp) / 'net.jsonl';log.write_text('{}\n' * (MAX_LOG_LINES + 10))
            local = socket.socket();local.bind(('127.0.0.1', 0));local.listen()
            def serve():
                conn, _ = local.accept()
                with conn:
                    conn.recv(1000);conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 5\r\nConnection: close\r\n\r\nlocal')
            threading.Thread(target=serve, daemon=True).start()
            proxy = Proxy(log, 'offline').start()
            try:
                self.assertLessEqual(len(log.read_text().splitlines()), MAX_LOG_LINES // 2)
                port = local.getsockname()[1]
                with socket.create_connection(('127.0.0.1', proxy.port), timeout=5) as s:
                    s.sendall(f'GET http://127.0.0.1:{port}/state HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n'.encode())
                    reply = b''
                    while chunk := s.recv(1000):reply += chunk
                self.assertTrue(reply.endswith(b'local'), 'the game\'s own local service is not answered with {}')
                echo = socket.socket();echo.bind(('127.0.0.1', 0));echo.listen()
                tunnel = socket.create_connection(('127.0.0.1', proxy.port), timeout=5)
                tunnel.sendall(f'CONNECT 127.0.0.1:{echo.getsockname()[1]} HTTP/1.1\r\n\r\n'.encode())
                self.assertTrue(tunnel.recv(100).startswith(b'HTTP/1.1 200'))
            finally:proxy.stop()
            self.assertEqual(tunnel.recv(100), b'', 'stopping the proxy ends open tunnels')
            tunnel.close();echo.close();local.close()


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.root = pathlib.Path(self.temp.name);self.store = Store(self.root / 'data')
        self.apk = make_apk(self.root / 'g.apk', fixture=False)
    def tearDown(self):self.temp.cleanup()

    def test_folder_left_by_an_interrupted_import_is_replaced(self):
        from apk_revival.util import digest
        broken = self.store.directory(digest(self.apk)[:24]);(broken / 'originals').mkdir(parents=True)
        p = self.store.import_game(self.apk)
        self.assertTrue((broken / 'profile.json').exists());self.assertEqual(p['id'], broken.name)

    def test_profile_exists_before_the_game_folder_appears(self):
        seen = []
        real = pathlib.Path.rename
        def rename(path, target):
            seen.append((pathlib.Path(path) / 'profile.json').exists());return real(path, target)
        with patch.object(pathlib.Path, 'rename', rename):self.store.import_game(self.apk)
        self.assertEqual(seen, [True])

    def test_bundle_adds_its_obb_to_a_game_already_in_the_library(self):
        p = self.store.import_game(self.apk)
        xapk = bundle(self.root / 'Game.xapk', {'manifest.json': '{"package_name": "%s"}' % PACKAGE, 'base.apk': self.apk.read_bytes(),
                                                f'Android/obb/{PACKAGE}/main.1.{PACKAGE}.obb': b'obb data'})
        again = self.store.import_game(xapk)
        self.assertEqual(again['id'], p['id']);self.assertEqual(sorted(i['role'] for i in again['inputs']), ['base_apk', 'obb'])
        self.assertEqual(len(self.store.import_game(xapk)['inputs']), 2, 'importing the same bundle again adds nothing')


class OldCopiesTests(unittest.TestCase):
    def test_only_the_newest_previous_install_and_no_stale_staging_is_kept(self):
        from apk_revival.launcher.install import remove_old_copies
        with tempfile.TemporaryDirectory() as temp:
            home = pathlib.Path(temp);share = home / '.local/share';share.mkdir(parents=True)
            for i, name in enumerate(('apk-revival-app.previous', 'apk-revival-app.previous-1', 'apk-revival-app.previous-2')):
                (share / name).mkdir();os.utime(share / name, (1000 + i, 1000 + i))
            staged = home / '.cache/apk-revival/updates/staged-abc';staged.mkdir(parents=True)
            remove_old_copies(home)
            self.assertEqual(sorted(p.name for p in share.iterdir()), ['apk-revival-app.previous-2'])
            self.assertFalse(staged.exists())


class ControllerTests(unittest.TestCase):
    def pad(self, state, nested=None):
        try:
            os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
            from PySide6.QtWidgets import QApplication, QWidget
            from apk_revival.launcher import controller
        except ImportError:self.skipTest('PySide6 is not installed')
        self.app = QApplication.instance() or QApplication([])
        class Lib:
            ids = [7]
            def SDL_GameControllerUpdate(self):pass
            def SDL_GameControllerGetAttached(self, h):return 1
            def SDL_NumJoysticks(self):return len(self.ids)
            def SDL_JoystickGetDeviceInstanceID(self, i):return self.ids[i]
            def SDL_IsGameController(self, i):return 1
            def SDL_GameControllerOpen(self, i):return 100 + self.ids[i]
            def SDL_GameControllerName(self, h):return b'Pad'
            def SDL_GameControllerGetButton(self, h, n):return int(state.get(n, False))
            def SDL_GameControllerGetAxis(self, h, n):return 0
        pad = controller.Controller.__new__(controller.Controller)
        pad.window, pad.back, pad.options, pad.game_buttons = QWidget(), lambda: None, lambda: None, None
        pad.lib, pad.handles, pad.previous, pad.last_dir, pad.repeat, pad.connected = Lib(), {}, {}, None, 0, []
        return pad

    def test_a_press_that_opens_a_dialog_does_not_also_answer_it(self):
        state = {0: True};pad = self.pad(state);actions = []
        def dispatch(action):
            actions.append(action)
            if len(actions) == 1:pad.poll()  # A dialog's event loop polls again while A is still held.
        pad.dispatch = dispatch;pad.poll()
        self.assertEqual(actions, ['confirm'])

    def test_unplugging_a_controller_does_not_double_the_other(self):
        state = {0: True};pad = self.pad(state);pad.lib.ids = [7, 8]
        actions = [];pad.dispatch = actions.append;pad.poll()
        pad.lib.ids = [8]  # Pad 7 unplugged: pad 8 moves to device index 0.
        pad.lib.SDL_GameControllerGetAttached = lambda h: int(h != 107)
        pad.lib.SDL_GameControllerClose = lambda h: None
        state[0] = False;pad.poll();state[0] = True;pad.poll()
        self.assertEqual(sorted(pad.handles), [8]);self.assertEqual(actions.count('confirm'), 3, 'two pads, then one press each')

    def test_dropdowns_can_be_used_and_closed_with_the_controller(self):
        self.pad({})
        from PySide6.QtWidgets import QComboBox
        from apk_revival.launcher.controller import choose_in_dropdown
        combo = QComboBox()
        for name in ('Recent', 'Name', 'Added'):combo.addItem(name)
        combo.model().item(1).setEnabled(False)
        combo.view().setCurrentIndex(combo.model().index(0, 0))
        choose_in_dropdown(combo, 'down');choose_in_dropdown(combo, 'confirm')
        self.assertEqual(combo.currentText(), 'Added', 'disabled entries are skipped')
        choose_in_dropdown(combo, 'up');choose_in_dropdown(combo, 'back')
        self.assertEqual(combo.currentText(), 'Added', 'back closes without choosing')


if __name__ == '__main__':
    unittest.main()
