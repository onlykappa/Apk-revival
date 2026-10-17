"""Game plugins: optional, game-specific restoration adapters installed beside the app.

A plugin is a ZIP containing plugin.json and Python code under apk_revival/<package>/.
Installed plugins live in DATA/plugins/<name>/, so app updates never remove them.
The core app never imports a plugin by name; plugins register adapters.
"""
from __future__ import annotations
import importlib, json, pathlib, re, shutil, sys, tempfile, zipfile
from .util import RevivalError, atomic_json, inspect_zip

NAME = re.compile(r'[a-z][a-z0-9-]{1,40}')
MODULE = re.compile(r'apk_revival\.[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*')
loaded = {}    # plugin name -> {'version', 'source', 'module'}
problems = {}  # plugin name -> error text
provides = {}  # adapter name -> plugin name


def source_for(adapter_name):
    """Installed folder of the plugin that provides an adapter, or None for built-ins."""
    return loaded.get(provides.get(adapter_name), {}).get('source')


def read_manifest(folder):
    try:
        meta = json.loads((pathlib.Path(folder) / 'plugin.json').read_text())
    except (OSError, ValueError) as error:
        raise RevivalError('This plugin has no readable plugin.json.') from error
    if not isinstance(meta, dict) or not NAME.fullmatch(str(meta.get('name', ''))) or not MODULE.fullmatch(str(meta.get('module', ''))):
        raise RevivalError('This plugin description is invalid.')
    package = meta['module'].split('.')[1]
    core = pathlib.Path(__file__).parent
    # A plugin may add its own package but never take the name of a core module.
    if not isinstance(meta.get('version'), str) or package == 'launcher' or (core / (package + '.py')).exists():
        raise RevivalError('This plugin description is invalid.')
    return meta


def _register(module_name, register, name, version, source):
    module = importlib.import_module(module_name)
    def add(instance):
        register(instance)
        provides[instance.name] = name
    module.register(add)
    loaded[name] = {'version': version, 'source': source, 'module': module_name}


def load(register, folders=()):
    """Register plugins built into this copy, then plugins installed in folders.

    A built-in plugin is any core subpackage with a plugin.py. Source checkouts
    include them; the public Linux build leaves them out.
    """
    core = pathlib.Path(__file__).parent
    for package in sorted(p for p in core.iterdir() if (p / 'plugin.py').is_file()):
        if package.name in loaded:
            continue
        try:
            _register(f'apk_revival.{package.name}.plugin', register, package.name, None, None)
        except ImportError:
            pass
    import apk_revival
    for folder in folders:
        folder = pathlib.Path(folder)
        if not folder.is_dir():
            continue
        for plugin in sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.endswith(('.new', '.old'))):
            try:
                meta = read_manifest(plugin)
                if meta['name'] in loaded:
                    continue
                code = str(plugin / 'apk_revival')
                if code not in apk_revival.__path__:
                    apk_revival.__path__.append(code)
                _register(meta['module'], register, meta['name'], meta['version'], str(plugin))
                problems.pop(meta['name'], None)
            except Exception as error:  # A broken plugin must never stop the app from opening.
                problems[plugin.name] = str(error)
    return dict(loaded)


def install(archive, folder):
    """Install or replace a plugin from a ZIP; returns its manifest. Takes effect on restart."""
    archive, folder = pathlib.Path(archive), pathlib.Path(folder)
    names = inspect_zip(archive, max_total=256 * 1024**2)
    if 'plugin.json' not in names:
        raise RevivalError('This file is not an APK Revival game plugin.')
    with zipfile.ZipFile(archive) as z, tempfile.TemporaryDirectory() as temp:
        z.extract('plugin.json', temp)
        meta = read_manifest(temp)
        package = 'apk_revival/' + meta['module'].split('.')[1] + '/'
        for name in names:
            if name != 'plugin.json' and not name.startswith(package):
                raise RevivalError('This plugin contains files outside its own folder.')
        folder.mkdir(parents=True, exist_ok=True)
        staged = folder / (meta['name'] + '.new')
        if staged.exists():
            shutil.rmtree(staged)
        z.extractall(staged)
    target, old = folder / meta['name'], folder / (meta['name'] + '.old')
    if old.exists():
        shutil.rmtree(old)
    if target.exists():
        target.rename(old)
    staged.rename(target)
    if old.exists():
        shutil.rmtree(old)
    return meta


def build(package_dir, output, version, extra=None):
    """Write a plugin ZIP from a source package directory (used by release tooling)."""
    package_dir = pathlib.Path(package_dir)
    name = package_dir.name
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('plugin.json', json.dumps({'name': name, 'module': f'apk_revival.{name}.plugin', 'version': version}, indent=2))
        for path in sorted(package_dir.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and 'regression_tests' not in path.parts:
                z.write(path, f'apk_revival/{name}/' + str(path.relative_to(package_dir)))
        for arcname, source in (extra or {}).items():
            z.write(source, f'apk_revival/{name}/{arcname}')
    return output


def plugin_for(adapter_name):
    """By convention a plugin named X provides adapters named X-<version>."""
    return provides.get(adapter_name) or str(adapter_name).split('-')[0]


def asset_name(name, version):
    return f'APK-Revival-plugin-{name}-{version}.zip'


def download(name, version, folder, updater=None):
    """Download the official plugin published with this app version, verify, and install."""
    import hashlib
    from .launcher.updater import API, Updater
    updater = updater or Updater()
    tag = 'v' + version
    with updater.request(API + '/releases/tags/' + tag) as response:
        release = json.loads(response.read(4 * 1024 * 1024))
    assets = {a['name']: a for a in release.get('assets', [])}
    wanted = asset_name(name, version)
    if wanted not in assets or 'SHA256SUMS.txt' not in assets:
        raise RevivalError(f'No {name} plugin is published for APK Revival {version}.')
    with updater.request(assets['SHA256SUMS.txt']['url'], asset=True) as response:
        sums = response.read(65537).decode()
    expected = next((line.split()[0] for line in sums.splitlines() if line.strip().endswith(wanted)), None)
    if not expected:
        raise RevivalError('The published plugin has no checksum. Nothing was installed.')
    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / wanted
        digest = hashlib.sha256()
        with updater.request(assets[wanted]['url'], asset=True) as response, path.open('wb') as out:
            while block := response.read(1024 * 1024):
                digest.update(block)
                out.write(block)
        if digest.hexdigest() != expected:
            raise RevivalError('The downloaded plugin did not match its published checksum. Nothing was installed.')
        return install(path, folder)
