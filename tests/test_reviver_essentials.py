"""App bundles, generic Android save backups, library removal and per-game Steam shortcuts."""
import io, json, os, pathlib, struct, sys, tarfile, tempfile, unittest, zipfile
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_pipeline import make_apk
from apk_revival import android_saves
from apk_revival.store import Store
from apk_revival.util import RevivalError

PACKAGE = 'org.example.unknown'


def bundle(path, members):
    with zipfile.ZipFile(path, 'w') as z:
        for name, data in members.items():
            z.writestr(name, data)
    return path


class BundleImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = pathlib.Path(self.temp.name)
        self.base = make_apk(self.root / 'b.apk', fixture=False).read_bytes()
        self.split = make_apk(self.root / 's.apk', fixture=False, split=True).read_bytes()
        self.store = Store(self.root / 'data')
    def tearDown(self): self.temp.cleanup()

    def test_xapk_imports_base_splits_and_obb_with_bundle_title(self):
        xapk = bundle(self.root / 'Space Trader.xapk', {
            'manifest.json': json.dumps({'package_name': PACKAGE}),
            f'{PACKAGE}.apk': self.base, 'config.arm64_v8a.apk': self.split,
            f'Android/obb/{PACKAGE}/main.1.{PACKAGE}.obb': b'obb data', 'icon.png': b'x'})
        p = self.store.import_game(xapk)
        roles = sorted(i['role'] for i in p['inputs'])
        self.assertEqual(roles, ['base_apk', 'obb', 'split_apk'])
        self.assertEqual(p['title'], 'Space Trader')
        obb = next(i for i in p['inputs'] if i['role'] == 'obb')
        self.assertEqual(obb['name'], f'main.1.{PACKAGE}.obb')
        self.assertFalse(any(self.store.root.glob('bundle-*')), 'temporary extraction must be removed')
        self.assertEqual(self.store.import_game(xapk)['id'], p['id'], 'importing again returns the same game')

    def test_apks_prefers_splits_and_ignores_standalones(self):
        apks = bundle(self.root / 'game.apks', {'splits/base-master.apk': self.base, 'splits/base-arm64_v8a.apk': self.split,
                                                 'standalones/standalone-x86.apk': self.base, 'toc.pb': b''})
        p = self.store.import_game(apks)
        self.assertEqual(sorted(i['role'] for i in p['inputs']), ['base_apk', 'split_apk'])

    def test_two_base_apks_and_missing_base_are_rejected(self):
        other = make_apk(self.root / 'o.apk', fixture=False, version='2').read_bytes()
        with self.assertRaisesRegex(RevivalError, 'more than one base APK'):
            self.store.import_game(bundle(self.root / 'two.apkm', {'base.apk': self.base, 'other.apk': other}))
        with self.assertRaisesRegex(RevivalError, 'no base APK'):
            self.store.import_game(bundle(self.root / 'splits.apks', {'split.apk': self.split}))
        self.assertFalse((self.store.root / 'games').exists() and any((self.store.root / 'games').iterdir()))

    def test_mismatched_manifest_and_encrypted_bundles_are_rejected(self):
        with self.assertRaisesRegex(RevivalError, 'different app'):
            self.store.import_game(bundle(self.root / 'bad.xapk', {'manifest.json': json.dumps({'package_name': 'org.other.app'}), 'base.apk': self.base}))
        path = self.root / 'locked.apkm'
        with zipfile.ZipFile(path, 'w') as z:z.writestr('base.apk', self.base)
        # Python's writer clears the encryption flag; set it in both ZIP headers directly.
        raw = bytearray(path.read_bytes())
        # The stored APK has its own ZIP headers: patch the outer local header at
        # the start and the outer central directory entry, which comes last.
        raw[6] |= 0x1;raw[raw.rindex(b'PK\x01\x02') + 8] |= 0x1
        path.write_bytes(bytes(raw))
        with self.assertRaisesRegex(RevivalError, 'encrypted'):self.store.import_game(path)
        # An encrypted APK inside an otherwise normal bundle is a clear error, not a crash.
        inner = bytearray(self.base);inner[6] |= 0x1;inner[inner.rindex(b'PK\x01\x02') + 8] |= 0x1
        with self.assertRaisesRegex(RevivalError, '[Ee]ncrypted|No readable APK'):
            self.store.import_game(bundle(self.root / 'inner.xapk', {'base.apk': bytes(inner)}))

    def test_per_file_zip_limit_is_adjustable_for_large_obbs(self):
        from apk_revival.util import inspect_zip
        path = bundle(self.root / 'big.xapk', {'base.apk': self.base})
        with self.assertRaisesRegex(RevivalError, 'per file'):inspect_zip(path, max_member=10)
        self.assertEqual(inspect_zip(path, max_member=len(self.base)), ['base.apk'])

    def test_unsupported_extension_message_lists_bundle_types(self):
        path = self.root / 'game.zip'; path.write_bytes(self.base)
        with self.assertRaisesRegex(RevivalError, r'\.xapk'):self.store.import_game(path)


class FakeAndroid:
    """Records commands; simulates the guest's root shell, tar and adb transfers."""
    def __init__(self, installed=True, root=True, data=None, external=None, uid='10057'):
        self.installed, self.root, self.uid = installed, root, uid
        self.data = data if data is not None else {f'data/data/{PACKAGE}/shared_prefs/save.xml': b'<map/>'}
        self.external = external or {}
        self.commands, self.pushed, self.remote = [], [], {}
    def shell(self, *args, timeout=60):
        self.commands.append(args)
        if args[:2] == ('pm', 'path'):return 'package:/data/app/base.apk\n' if self.installed else ''
        if args[:3] == ('su', '0', 'id'):
            if not self.root:raise RevivalError('su: permission denied')
            return '0\n'
        if args[:4] == ('su', '0', 'sh', '-c'):
            script = args[4]
            if script.startswith('[ -d /data/data/'):return 'yes' if self.data else 'no'
            if script.startswith('[ -d /data/media/'):return 'yes' if self.external else 'no'
            if script.startswith('stat -c %u'):return self.uid
            if 'tar -cf' in script:
                remote = script.split('tar -cf ')[1].split()[0]
                self.remote[remote] = self.external if 'data/media' in script else self.data
            return ''
        return ''
    def adb(self, *args, timeout=60):
        self.commands.append(('adb',) + args)
        if args[0] == 'pull':
            with tarfile.open(args[2], 'w') as out:
                for name, value in self.remote[args[1]].items():
                    info = tarfile.TarInfo(name)
                    if value is None:info.type = tarfile.SYMTYPE; info.linkname = '/etc'; out.addfile(info)
                    else:info.size = len(value); out.addfile(info, io.BytesIO(value))
        if args[0] == 'push':
            with tarfile.open(args[1]) as archive:self.pushed.append(sorted(m.name for m in archive.getmembers()))
        if args[0] == 'uninstall':self.installed = False
        return 'Success'


def profile(package=PACKAGE):
    return {'id': 'a' * 24, 'apk_sha256': 'b' * 64, 'restoration': {}, 'analysis': {'metadata': {'package': package, 'version_code': '7'}}}


class AndroidSaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = pathlib.Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def test_backup_skips_caches_and_records_both_data_folders(self):
        android = FakeAndroid(external={f'data/media/0/Android/data/{PACKAGE}/files/slot1.dat': b'progress'})
        path = android_saves.backup(android, profile(), self.root / 'b.zip')
        scripts = [c[4] for c in android.commands if c[:4] == ('su', '0', 'sh', '-c')]
        internal = next(s for s in scripts if 'tar -cf' in s and 'data/data' in s)
        for skipped in ('cache', 'code_cache', 'lib'):self.assertIn(f'--exclude=data/data/{PACKAGE}/{skipped}', internal)
        self.assertIn(('am', 'force-stop', PACKAGE), android.commands)
        self.assertTrue(any('rm -f /data/local/tmp/apkr-' in s for s in scripts), 'temporary guest archives are deleted')
        with zipfile.ZipFile(path) as z:
            meta = json.loads(z.read('backup.json'))
            self.assertEqual(sorted(meta['files']), ['data.tar', 'external.tar'])
            self.assertEqual((meta['kind'], meta['package'], meta['version_code']), ('android', PACKAGE, '7'))

    def test_backup_requires_installed_game_root_and_data(self):
        with self.assertRaisesRegex(RevivalError, 'not installed'):android_saves.backup(FakeAndroid(installed=False), profile(), self.root / 'x.zip')
        with self.assertRaisesRegex(RevivalError, 'root access'):android_saves.backup(FakeAndroid(root=False), profile(), self.root / 'x.zip')
        with self.assertRaisesRegex(RevivalError, 'No saved data'):android_saves.backup(FakeAndroid(data={}), profile(), self.root / 'x.zip')

    def test_backup_stops_if_android_returns_files_outside_the_game(self):
        android = FakeAndroid(data={'data/data/org.evil.app/x': b'1'})
        with self.assertRaisesRegex(RevivalError, 'outside'):android_saves.backup(android, profile(), self.root / 'x.zip')

    def test_restore_drops_links_fixes_owner_and_selinux(self):
        android = FakeAndroid(data={f'data/data/{PACKAGE}/shared_prefs/save.xml': b'<map/>', f'data/data/{PACKAGE}/shared_prefs/escape': None})
        path = android_saves.backup(android, profile(), self.root / 'b.zip')
        result = android_saves.restore(android, profile(), path)
        self.assertTrue(result['restored'])
        self.assertEqual(android.pushed, [[f'data/data/{PACKAGE}/shared_prefs/save.xml']], 'links are never sent back to Android')
        script = next(c[4] for c in android.commands if c[:4] == ('su', '0', 'sh', '-c') and 'tar -xf' in c[4])
        self.assertIn('chown -R 10057:10057', script); self.assertIn('restorecon -R', script); self.assertIn('! -name lib', script)

    def test_restore_rejects_other_games_damage_and_escapes(self):
        android = FakeAndroid()
        path = pathlib.Path(android_saves.backup(android, profile(), self.root / 'b.zip'))
        with self.assertRaisesRegex(RevivalError, 'belongs to'):android_saves.restore(android, profile('org.other.app'), path)
        damaged = self.root / 'damaged.zip'
        with zipfile.ZipFile(path) as z, zipfile.ZipFile(damaged, 'w') as out:
            out.writestr('backup.json', z.read('backup.json')); out.writestr('data.tar', z.read('data.tar') + b'x')
        with self.assertRaisesRegex(RevivalError, 'damaged'):android_saves.restore(android, profile(), damaged)
        escape = self.root / 'escape.zip'; tar = self.root / 'e.tar'
        with tarfile.open(tar, 'w') as out:
            info = tarfile.TarInfo(f'data/data/{PACKAGE}/../../../system/x'); info.size = 1; out.addfile(info, io.BytesIO(b'1'))
        with zipfile.ZipFile(escape, 'w') as out:
            out.write(tar, 'data.tar')
            out.writestr('backup.json', json.dumps({'schema_version': 1, 'kind': 'android', 'package': PACKAGE, 'files': {'data.tar': android_saves._sha256(tar)}}))
        with self.assertRaisesRegex(RevivalError, 'outside'):android_saves.restore(android, profile(), escape)
        self.assertEqual(android.pushed, [], 'nothing reaches Android after a rejected backup')


class RemoveAndSteamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = pathlib.Path(self.temp.name)
        self.store = Store(self.root / 'data')
        self.p = self.store.import_game(make_apk(self.root / 'Game.apk', fixture=False))
        from apk_revival.analysis import analyze
        self.p = analyze(self.store, self.p['id'])
    def tearDown(self): self.temp.cleanup()

    def launcher(self, android):
        from apk_revival.launcher.service import Launcher
        launcher = Launcher(self.store)
        launcher.runtime_manager.ensure = lambda *a, **k: 'guest:5555'
        launcher.runtime_factory = lambda serial: android
        return launcher

    class Ctx:
        def step(self, *a):pass

    def test_remove_keeps_saves_and_backups(self):
        d = self.store.directory(self.p['id']);(d / 'backups').mkdir();(d / 'backups/old.zip').write_bytes(b'z')
        kept = pathlib.Path(self.store.remove(self.p['id']))
        self.assertFalse(d.exists());self.assertTrue((kept / 'backups/old.zip').exists())
        self.assertEqual(json.loads((kept / 'removed.json').read_text())['id'], self.p['id'])
        other = self.store.import_game(make_apk(self.root / 'Other.apk', fixture=False, package='org.example.other'))
        self.assertIsNone(self.store.remove(other['id']), 'nothing to keep, nothing created')

    def test_uninstall_backs_up_progress_first(self):
        android = FakeAndroid()
        result = self.launcher(android).remove_game(self.p['id'], True, self.Ctx())
        self.assertTrue(result['uninstalled']);self.assertFalse(android.installed)
        order = [c[0] if c[0] != 'su' else 'backup' for c in android.commands if c[0] in ('adb', 'su')]
        self.assertLess(order.index('backup'), max(i for i, c in enumerate(android.commands) if c[:2] == ('adb', 'uninstall')))
        self.assertTrue(list(pathlib.Path(result['kept'], 'backups').glob('*before-uninstall.zip')))

    def test_failed_backup_cancels_uninstall_and_removal(self):
        android = FakeAndroid(root=False)
        with self.assertRaisesRegex(RevivalError, 'not removed'):self.launcher(android).remove_game(self.p['id'], True, self.Ctx())
        self.assertTrue(android.installed);self.assertTrue(self.store.directory(self.p['id']).exists())

    def test_running_game_cannot_be_removed(self):
        launcher = self.launcher(FakeAndroid());launcher.active = {'game': self.p['id']}
        with self.assertRaisesRegex(RevivalError, 'Stop this game'):launcher.remove_game(self.p['id'], False, self.Ctx())

    def test_generic_backup_and_restore_through_the_service(self):
        android = FakeAndroid();launcher = self.launcher(android)
        path = launcher.backup(self.p['id'], self.Ctx())
        self.assertEqual(launcher.backups(self.p['id'])[0], pathlib.Path(path))
        result = launcher.restore(self.p['id'], path, self.Ctx())
        self.assertTrue(result['restored']);self.assertTrue(result['previous_backup'].endswith('before-restore.zip'))

    def test_steam_shortcut_per_game(self):
        from apk_revival.launcher.steam import parse, register
        home = self.root / 'home';config = home / '.local/share/Steam/userdata/42/config';config.mkdir(parents=True)
        exe = home / '.local/share/apk-revival-app/APK-Revival'
        self.assertTrue(register(exe, home)['registered'])
        game = register(exe, home, name='Space Trader', launch_options='--fullscreen --play ' + self.p['id'], icon='/x/icon.png')
        self.assertTrue(game['registered']);self.assertNotIn('already_present', game)
        again = register(exe, home, name='Space Trader', launch_options='--fullscreen --play ' + self.p['id'])
        self.assertTrue(again['already_present'])
        records = parse((config / 'shortcuts.vdf').read_bytes())[0][2]
        fields = [{label.decode().lower(): value for typ, label, value in entry} for kind, idx, entry in records]
        self.assertEqual([f['appname'] for f in fields], [b'APK Revival', b'Space Trader'])
        self.assertEqual(fields[1]['launchoptions'], ('--fullscreen --play ' + self.p['id']).encode());self.assertEqual(fields[1]['icon'], b'/x/icon.png')
        (home / '.steam').mkdir();(home / '.steam/steam.pid').write_text(str(os.getpid()))
        self.assertFalse(register(exe, home, name='Other', launch_options='--fullscreen --play ' + 'c' * 24)['registered'])

    def test_steam_needs_packaged_app(self):
        with self.assertRaisesRegex(RevivalError, 'packaged'):self.launcher(FakeAndroid()).add_to_steam(self.p['id'])


if __name__ == '__main__':
    unittest.main()
