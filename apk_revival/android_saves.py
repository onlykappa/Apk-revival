"""Back up and restore any Android game's progress through guest root.

Covers the app's private data (/data/data/PACKAGE, without caches and native
libraries) and its external app folder, where engines such as Unity keep saves
(/data/media/0/Android/data/PACKAGE). Expansion OBBs are reinstallable and are not
included. Backups are local ZIP files and are never part of a game export.
"""
from __future__ import annotations
import hashlib, json, pathlib, re, shlex, tarfile, tempfile, uuid, zipfile
from .util import RevivalError, inspect_zip, now

PACKAGE = re.compile(r'[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+')
SKIPPED = ('cache', 'code_cache', 'lib')
TEMP = '/data/local/tmp'
MAX_BACKUP = 32 * 1024**3  # Backups are written by APK Revival itself; large asset folders are common.


def package_for(p):
    """The Android package that is actually installed for this library entry."""
    rest = p.get('restoration') or {}
    package = rest.get('client_package') if rest.get('artifact') else None
    package = package or ((p.get('analysis') or {}).get('metadata') or {}).get('package')
    if not isinstance(package, str) or not PACKAGE.fullmatch(package):
        raise RevivalError('This game has no valid Android package name. Add it again from its APK.')
    return package


def roots(package):
    return {'data.tar': ('/', f'data/data/{package}'), 'external.tar': ('/', f'data/media/0/Android/data/{package}')}


def _root(runtime, *command, timeout=120):
    return runtime.shell('su', '0', 'sh', '-c', ' '.join(command), timeout=timeout)


def _require(runtime, package):
    if 'package:' not in runtime.shell('pm', 'path', package, timeout=20):
        raise RevivalError('This game is not installed in Android yet. Press Play once, then back up its progress.')
    try:
        uid = runtime.shell('su', '0', 'id', '-u', timeout=10).strip()
    except RevivalError as error:
        raise RevivalError('Android root access is needed to back up game progress, and it was refused.') from error
    if uid != '0':
        raise RevivalError('Android root access is needed to back up game progress, and it was refused.')


def backup(runtime, p, target):
    """Write a backup ZIP of the game's Android data to target and return its path."""
    package = package_for(p)
    _require(runtime, package)
    runtime.shell('am', 'force-stop', package, timeout=10)
    target = pathlib.Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Written aside and renamed when complete, so a failed backup never looks like a real one.
    partial = target.with_name(target.name + '.partial')
    try:
        _write_backup(runtime, p, package, partial)
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return str(target)


def _write_backup(runtime, p, package, target):
    files = {}
    with tempfile.TemporaryDirectory() as temp, zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for name, (cwd, path) in roots(package).items():
            exists = _root(runtime, f'[ -d /{shlex.quote(path)} ] && echo yes || echo no', timeout=10).strip()
            if exists != 'yes':
                continue
            remote = f'{TEMP}/apkr-{uuid.uuid4().hex}.tar'
            excludes = ' '.join(f'--exclude={shlex.quote(path + "/" + skip)}' for skip in SKIPPED) if name == 'data.tar' else ''
            try:
                _root(runtime, f'cd {cwd} && tar -cf {remote} {excludes} {shlex.quote(path)} && chmod 644 {remote}', timeout=600)
                local = pathlib.Path(temp) / name
                runtime.adb('pull', remote, str(local), timeout=900)
            finally:
                try:
                    _root(runtime, f'rm -f {remote}', timeout=10)
                except RevivalError:
                    pass
            check_paths(local, path)
            z.write(local, name)
            files[name] = _sha256(local)
        if not files:
            raise RevivalError('No saved data exists for this game yet.')
        version = (((p.get('analysis') or {}).get('metadata') or {}).get('version_code'))
        z.writestr('backup.json', json.dumps({'schema_version': 1, 'kind': 'android', 'package': package,
                                              'version_code': version, 'apk_sha256': p.get('apk_sha256'),
                                              'time': now(), 'files': files}, indent=2))


def read_meta(backup_zip):
    try:
        with zipfile.ZipFile(backup_zip) as z:
            return json.loads(z.read('backup.json'))
    except (KeyError, ValueError, zipfile.BadZipFile) as error:
        raise RevivalError('This is not an APK Revival save backup.') from error


def restore(runtime, p, backup_zip):
    """Replace the game's Android data with a validated backup."""
    package = package_for(p)
    inspect_zip(backup_zip, max_total=MAX_BACKUP, max_member=MAX_BACKUP)  # Each part is one large tar.
    meta = read_meta(backup_zip)
    if meta.get('schema_version') != 1 or meta.get('kind') != 'android':
        raise RevivalError('This backup is not an Android game backup.')
    if meta.get('package') != package:
        raise RevivalError(f'This backup belongs to {meta.get("package")}, not {package}.')
    files = meta.get('files')
    if not isinstance(files, dict) or not files or not set(files) <= set(roots(package)):
        raise RevivalError('This backup lists unexpected files.')
    _require(runtime, package)
    runtime.shell('am', 'force-stop', package, timeout=10)
    data_dir = f'/data/data/{package}'
    uid = _root(runtime, f'stat -c %u {shlex.quote(data_dir)}', timeout=10).strip()
    if not uid.isdigit():
        raise RevivalError('Could not read the game\'s Android user. Nothing was restored.')
    with tempfile.TemporaryDirectory() as temp, zipfile.ZipFile(backup_zip) as z:
        local = {}
        for name, expected in files.items():
            path = pathlib.Path(temp) / name
            with z.open(name) as source, path.open('wb') as out:
                while block := source.read(1024 * 1024):
                    out.write(block)
            if _sha256(path) != expected:
                raise RevivalError('This backup is damaged (checksum mismatch). Nothing was restored.')
            clean = pathlib.Path(temp) / ('clean-' + name)
            filtered_copy(path, clean, roots(package)[name][1])
            local[name] = clean
        for name, path in local.items():
            cwd, folder = roots(package)[name]
            remote = f'{TEMP}/apkr-{uuid.uuid4().hex}.tar'
            runtime.adb('push', str(path), remote, timeout=900)
            target = '/' + folder
            keep = ' '.join(f'! -name {skip}' for skip in SKIPPED) if name == 'data.tar' else ''
            owner = f'find {shlex.quote(target)} -mindepth 1 -maxdepth 1 {keep} -exec chown -R {uid}:{uid} {{}} +' if name == 'data.tar' \
                else f'chown -R {uid} {shlex.quote(target)}'
            try:
                _root(runtime,
                      f'mkdir -p {shlex.quote(target)} && '
                      f'find {shlex.quote(target)} -mindepth 1 -maxdepth 1 {keep} -exec rm -rf {{}} + && '
                      f'cd {cwd} && tar -xf {remote} && {owner} && (restorecon -R {shlex.quote(target)} || true)',
                      timeout=600)
            finally:
                try:
                    _root(runtime, f'rm -f {remote}', timeout=10)
                except RevivalError:
                    pass
    return {'restored': True, 'package': package}


def _inside(member, folder):
    name = member.name.removeprefix('./')
    parts = pathlib.PurePosixPath(name).parts
    return not name.startswith('/') and '..' not in parts and (name == folder or name.startswith(folder + '/'))


def check_paths(path, folder):
    """Every entry must sit inside the game's own data folder."""
    try:
        with tarfile.open(path) as archive:
            for member in archive.getmembers():
                if not _inside(member, folder):
                    raise RevivalError('Android returned files outside the game\'s data folder. Backup stopped.')
    except tarfile.TarError as error:
        raise RevivalError('The backup archive from Android could not be read.') from error


def filtered_copy(source, target, folder):
    """Rebuild an archive holding only regular files and folders inside folder.

    Links and device entries are dropped, so a backup can never write outside
    the game's data through a link, whoever made the file.
    """
    try:
        with tarfile.open(source) as archive, tarfile.open(target, 'w') as out:
            for member in archive.getmembers():
                if not _inside(member, folder):
                    raise RevivalError('This backup contains files outside the game\'s data folder. Nothing was restored.')
                if member.isdir():
                    out.addfile(member)
                elif member.isfile():
                    out.addfile(member, archive.extractfile(member))
    except tarfile.TarError as error:
        raise RevivalError('This backup archive could not be read. Nothing was restored.') from error


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()
