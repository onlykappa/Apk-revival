"""Play time, library sorting, crash logs, Steam artwork and per-game display settings."""
import os, pathlib, tempfile, time, unittest
from unittest.mock import patch
from apk_revival import display
from apk_revival.store import Store
from apk_revival.util import RevivalError


class Ctx:
    def step(self, *a):pass


def launcher(root):
    from apk_revival.launcher.service import Launcher
    return Launcher(Store(pathlib.Path(root)))


def add_game(service, root, package='org.example.unknown'):
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from test_pipeline import make_apk
    from apk_revival.analysis import analyze
    p = service.store.import_game(make_apk(pathlib.Path(root) / (package + '.apk'), fixture=False, package=package))
    return analyze(service.store, p['id'])


class PlaytimeAndSortTests(unittest.TestCase):
    def test_stop_adds_session_time(self):
        with tempfile.TemporaryDirectory() as temp:
            service = launcher(temp);p = add_game(service, temp)
            start = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - 125))
            service.active = {'game': p['id'], 'kind': 'android', 'started_at': start}
            service.runtime_manager.stop_owned_session = lambda: None
            service.stop();service.active = {'game': p['id'], 'kind': 'android', 'started_at': start};service.stop()
            seconds = service.store.load(p['id'])['launcher']['playtime_seconds']
            self.assertTrue(240 <= seconds <= 260, seconds)
            from apk_revival.launcher.metadata import details, playtime
            self.assertEqual(playtime(seconds), '4 min')
            self.assertIn(('Play time', '4 min'), details(service.store.load(p['id'])))

    def test_sort_orders(self):
        try:from apk_revival.launcher.ui import sort_games
        except ImportError:self.skipTest('PySide6 is not installed')
        games = [{'title': 'beta', 'created_at': '2026-01-02', 'launcher': {'last_played': '2026-02-01'}, 'analysis': None},
                 {'title': 'Alpha', 'created_at': '2026-01-03', 'launcher': {}, 'analysis': None},
                 {'title': 'gamma', 'created_at': '2026-01-01', 'launcher': {'last_played': '2026-03-01'}, 'analysis': None}]
        self.assertEqual([g['title'] for g in sort_games(games, 'name')], ['Alpha', 'beta', 'gamma'])
        self.assertEqual([g['title'] for g in sort_games(games, 'added')], ['Alpha', 'beta', 'gamma'])
        self.assertEqual([g['title'] for g in sort_games(games, 'recent')], ['gamma', 'beta', 'Alpha'])


class CrashLogTests(unittest.TestCase):
    class Android:
        package = 'org.example.unknown'
        def __init__(self, crash, main=''):self.crash, self.main, self.cleared = crash, main, False
        def adb(self, *args, timeout=60):
            if args[:4] == ('logcat', '-b', 'crash', '-c'):self.cleared = True;return ''
            return self.crash if '-b' in args else self.main

    def test_crash_naming_the_game_is_saved_and_others_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            service = launcher(temp);p = add_game(service, temp)
            android = self.Android('E AndroidRuntime: FATAL EXCEPTION: main\nE AndroidRuntime: Process: org.example.unknown, PID: 4242\n')
            service.clear_crash_buffer(android);self.assertTrue(android.cleared)
            path = service.capture_crash(p['id'], android, 'The game process ended while playing.')
            self.assertIn('FATAL EXCEPTION', path.read_text());self.assertEqual(service.crash_logs(p['id']), [path])
            self.assertIsNone(service.capture_crash(p['id'], self.Android('E AndroidRuntime: Process: com.other.app\n'), 'x'))

    def test_capture_never_raises(self):
        with tempfile.TemporaryDirectory() as temp:
            service = launcher(temp)
            class Broken:
                package = 'x.y'
                def adb(self, *a, **k):raise RevivalError('adb gone')
            self.assertIsNone(service.capture_crash('a' * 24, Broken(), 'x'))


class SteamArtworkTests(unittest.TestCase):
    def test_artwork_is_written_for_new_and_existing_shortcuts(self):
        from apk_revival.launcher.steam import register
        with tempfile.TemporaryDirectory() as temp:
            home = pathlib.Path(temp);config = home / '.local/share/Steam/userdata/7/config';config.mkdir(parents=True)
            art = {}
            for suffix in ('p', '', '_hero', 'bogus'):
                art[suffix] = home / f'art{suffix}.png';art[suffix].write_bytes(b'\x89PNG' + suffix.encode())
            first = register(home / 'APK-Revival', home, name='Game', launch_options='--fullscreen --play ' + 'b' * 24, artwork=art)
            appid = first['appid']
            self.assertEqual(sorted(pathlib.Path(p).name for p in first['artwork']), sorted([f'{appid}p.png', f'{appid}.png', f'{appid}_hero.png']))
            (config / 'grid' / f'{appid}p.png').unlink()
            again = register(home / 'APK-Revival', home, name='Game', launch_options='--fullscreen --play ' + 'b' * 24, artwork=art)
            self.assertTrue(again['already_present']);self.assertTrue((config / 'grid' / f'{appid}p.png').exists())


class FakeAndroid:
    def __init__(self, density='Physical density: 240\n', rotation=('1', '0')):
        self.commands, self.density, self.values = [], density, dict(zip(('accelerometer_rotation', 'user_rotation'), rotation))
    def shell(self, *args, timeout=60):
        self.commands.append(args)
        if args == ('wm', 'density'):return self.density
        if args[:3] == ('settings', 'get', 'system'):return self.values[args[3]]
        return ''


class DisplayTests(unittest.TestCase):
    def test_apply_and_restore(self):
        android = FakeAndroid()
        p = {'launcher': {'display': {'size': 'smaller', 'landscape': True}}}
        remembered = []
        previous = display.apply(android, p, remembered.append)
        self.assertEqual(remembered, [previous])
        self.assertIn(('wm', 'density', '192'), android.commands)
        self.assertIn(('settings', 'put', 'system', 'user_rotation', '1'), android.commands)
        display.restore(android, previous)
        self.assertIn(('wm', 'density', 'reset'), android.commands)
        self.assertIn(('settings', 'put', 'system', 'accelerometer_rotation', '1'), android.commands)

    def test_default_changes_nothing_and_override_is_kept(self):
        android = FakeAndroid('Physical density: 240\nOverride density: 200\n')
        self.assertIsNone(display.apply(android, {'launcher': {}}));self.assertEqual(android.commands, [])
        previous = display.apply(android, {'launcher': {'display': {'size': 'larger'}}})
        self.assertEqual(previous, {'density': 200});self.assertIn(('wm', 'density', '300'), android.commands)
        display.restore(android, previous);self.assertIn(('wm', 'density', '200'), android.commands)

    def test_service_restores_leftovers_from_a_crash(self):
        with tempfile.TemporaryDirectory() as temp:
            service = launcher(temp);service.settings['display_restore'] = {'density': None}
            android = FakeAndroid();service.start_display({'launcher': {}}, android, Ctx())
            self.assertIn(('wm', 'density', 'reset'), android.commands);self.assertIsNone(service.settings['display_restore'])
            service.start_display({'launcher': {'display': {'landscape': True}}}, android, Ctx())
            self.assertEqual(service.settings['display_restore'], {'accelerometer_rotation': '1', 'user_rotation': '0'})
            service.stop_display();self.assertIsNone(service.settings['display_restore'])
            self.assertIn(('settings', 'put', 'system', 'user_rotation', '0'), android.commands)


if __name__ == '__main__':
    unittest.main()
