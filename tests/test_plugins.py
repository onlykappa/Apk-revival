"""Game plugins: the core app runs without them, and installed plugin files restore support."""
import json, os, pathlib, shutil, subprocess, sys, tempfile, textwrap, unittest, zipfile
from apk_revival import plugins
from apk_revival.util import RevivalError

ROOT = pathlib.Path(__file__).resolve().parents[1]


class CoreWithoutMeegoTests(unittest.TestCase):
    """Runs in a separate Python process against a copy of the app with no Meego code."""
    def test_core_runs_without_meego_and_the_plugin_file_restores_it(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = pathlib.Path(temp)
            shutil.copytree(ROOT / 'apk_revival', temp / 'core/apk_revival', ignore=shutil.ignore_patterns('meego', '__pycache__'))
            plugin = plugins.build(ROOT / 'apk_revival/meego', temp / 'meego.zip', '9.9.9', {'meego-starter.json': ROOT / 'resources/meego-starter.json'})
            script = textwrap.dedent(f'''
                import json, pathlib, sys
                sys.path.insert(0, {str(temp / "core")!r})
                from apk_revival import adapters, plugins
                from apk_revival.launcher.presentation import readiness
                import apk_revival.launcher.service, apk_revival.restoration, apk_revival.runtime
                result = {{"before": sorted(adapters.ADAPTERS)}}
                profile = {{"adapter": "meego-1.32", "analysis": {{"input_errors": []}}, "restoration": {{}}}}
                result["missing"] = adapters.missing_plugin(profile)
                result["label"] = readiness(profile)["label"]
                try:
                    adapters.adapter(profile)
                except Exception as error:
                    result["error"] = str(error)
                plugins.install({str(plugin)!r}, {str(temp / "plugins")!r})
                adapters.load_plugins({str(temp / "plugins")!r})
                result["after"] = sorted(adapters.ADAPTERS)
                result["source"] = plugins.source_for("meego-1.32")
                import apk_revival.meego.backend as backend, apk_revival.meego.adapter as meego_adapter
                result["backend_from"] = backend.__file__
                result["starter_beside_code"] = (pathlib.Path(meego_adapter.__file__).with_name("meego-starter.json")).is_file()
                result["ready"] = readiness(profile)["label"]
                print(json.dumps(result))
            ''')
            env = dict(os.environ, PYTHONPATH='')
            run = subprocess.run([sys.executable, '-c', script], cwd=temp, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout.strip().splitlines()[-1])
            self.assertEqual(result['before'], ['tapquest-v1'], 'the core app has no Meego support of its own')
            self.assertEqual((result['missing'], result['label']), ('meego', 'Game plugin needed'))
            self.assertIn('Setup > Game plugins', result['error'])
            self.assertEqual(result['after'], ['meego-1.32', 'tapquest-v1'])
            self.assertTrue(result['source'].endswith('plugins/meego'))
            self.assertIn(str(temp / 'plugins/meego'), result['backend_from'])
            self.assertTrue(result['starter_beside_code'])
            self.assertNotEqual(result['ready'], 'Game plugin needed')

    def test_core_source_never_imports_meego_directly(self):
        offenders = [str(path.relative_to(ROOT)) for path in (ROOT / 'apk_revival').rglob('*.py')
                     if 'meego' not in path.relative_to(ROOT / 'apk_revival').parts and 'meego' in path.read_text().lower()]
        self.assertEqual(offenders, [])


class PluginFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = pathlib.Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def plugin(self, name='demo', module='apk_revival.demo.plugin', members=None, version='1.0.0'):
        path = self.root / f'{name}-{version}.zip'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('plugin.json', json.dumps({'name': name, 'module': module, 'version': version}))
            for member, data in (members if members is not None else {'apk_revival/demo/__init__.py': '', 'apk_revival/demo/plugin.py': 'def register(add):pass\n'}).items():
                z.writestr(member, data)
        return path

    def test_install_and_replace(self):
        folder = self.root / 'plugins'
        self.assertEqual(plugins.install(self.plugin(), folder)['version'], '1.0.0')
        self.assertEqual(plugins.install(self.plugin(version='1.1.0'), folder)['version'], '1.1.0')
        self.assertEqual(json.loads((folder / 'demo/plugin.json').read_text())['version'], '1.1.0')
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ['demo'])

    def test_rejects_unsafe_or_invalid_plugins(self):
        folder = self.root / 'plugins'
        with self.assertRaisesRegex(RevivalError, 'outside its own folder'):
            plugins.install(self.plugin(members={'apk_revival/demo/plugin.py': '', 'apk_revival/util.py': 'x'}), folder)
        with self.assertRaisesRegex(RevivalError, 'invalid'):plugins.install(self.plugin(name='Bad Name'), folder)
        with self.assertRaisesRegex(RevivalError, 'invalid'):
            plugins.install(self.plugin(module='apk_revival.launcher.plugin', members={'apk_revival/launcher/plugin.py': ''}), folder)
        with self.assertRaisesRegex(RevivalError, 'invalid'):
            plugins.install(self.plugin(module='apk_revival.util.plugin', members={'apk_revival/util/plugin.py': ''}), folder)
        bare = self.root / 'bare.zip'
        with zipfile.ZipFile(bare, 'w') as z:z.writestr('readme.txt', 'x')
        with self.assertRaisesRegex(RevivalError, 'not an APK Revival game plugin'):plugins.install(bare, folder)
        self.assertFalse(folder.exists() and any(folder.iterdir()))

    def test_broken_installed_plugin_is_reported_not_fatal(self):
        folder = self.root / 'plugins' / 'broken';folder.mkdir(parents=True);(folder / 'plugin.json').write_text('{not json')
        plugins.load(lambda adapter: None, [self.root / 'plugins'])
        self.assertIn('broken', plugins.problems);plugins.problems.pop('broken')

    def test_download_verifies_the_published_checksum(self):
        import hashlib, io
        from apk_revival.launcher.updater import API
        data = self.plugin(version='0.6.0').read_bytes();name = plugins.asset_name('demo', '0.6.0')
        def fake(sums):
            class Updater:
                def request(self, url, asset=False):
                    body = {API + '/releases/tags/v0.6.0': json.dumps({'assets': [{'name': name, 'url': API + '/a/1'}, {'name': 'SHA256SUMS.txt', 'url': API + '/a/2'}]}).encode(),
                            API + '/a/2': sums.encode(), API + '/a/1': data}[url]
                    return io.BytesIO(body)
            return Updater()
        folder = self.root / 'plugins'
        with self.assertRaisesRegex(RevivalError, 'did not match'):plugins.download('demo', '0.6.0', folder, fake('0' * 64 + '  ' + name + '\n'))
        self.assertFalse((folder / 'demo').exists())
        meta = plugins.download('demo', '0.6.0', folder, fake(hashlib.sha256(data).hexdigest() + '  ' + name + '\n'))
        self.assertEqual(meta['version'], '0.6.0');self.assertTrue((folder / 'demo/plugin.json').exists())
        with self.assertRaisesRegex(RevivalError, 'No other plugin'):plugins.download('other', '0.6.0', folder, fake(''))

    def test_plugin_name_convention(self):
        self.assertEqual(plugins.plugin_for('meego-1.32'), 'meego')
        self.assertEqual(plugins.asset_name('meego', '0.6.0'), 'APK-Revival-plugin-meego-0.6.0.zip')


if __name__ == '__main__':
    unittest.main()
