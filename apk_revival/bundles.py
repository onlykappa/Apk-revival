"""Unpack XAPK, APKS and APKM app bundles into a base APK, split APKs and OBBs.

Bundles are untrusted ZIP archives. Only .apk and .obb members are extracted, under
flat sanitized names, within size limits. The originals are never modified.
"""
from __future__ import annotations
import json, pathlib, re, shutil, zipfile
from .util import RevivalError, inspect_zip

BUNDLE_TYPES = ('.xapk', '.apks', '.apkm')
MAX_BUNDLE = 16 * 1024**3
MAX_MEMBERS = 2000


def is_bundle(path):
    return pathlib.Path(path).suffix.lower() in BUNDLE_TYPES


def _manifest(data):
    from .analysis import manifest
    return manifest(data)


def unpack(bundle, destination):
    """Extract a bundle; return {'base': path, 'splits': [paths], 'obbs': [paths]}."""
    bundle = pathlib.Path(bundle)
    destination = pathlib.Path(destination)
    try:
        with zipfile.ZipFile(bundle) as z:
            if any(info.flag_bits & 0x1 for info in z.infolist()):
                raise RevivalError('This bundle is encrypted. APK Revival can only open unencrypted XAPK, APKS and APKM files.')
        names = inspect_zip(bundle, max_total=MAX_BUNDLE, max_member=MAX_BUNDLE)  # OBBs are often several GB
    except zipfile.BadZipFile as error:
        raise RevivalError('This bundle is not a readable ZIP archive. Download it again or use its APK.') from error
    if len(names) > MAX_MEMBERS:
        raise RevivalError('This bundle contains too many files to import safely.')
    with zipfile.ZipFile(bundle) as z:
        apks = [n for n in names if n.lower().endswith('.apk') and not n.endswith('/')]
        # bundletool APKS archives also carry standalone APKs for old devices.
        # Prefer the split set when both exist.
        if any(n.startswith('splits/') for n in apks):
            apks = [n for n in apks if not n.startswith('standalones/')]
        obbs = [n for n in names if n.lower().endswith('.obb') and not n.endswith('/')]
        if not apks:
            raise RevivalError('No APK was found inside this bundle.')
        destination.mkdir(parents=True, exist_ok=True)
        used = set()

        def extract(member, folder):
            name = re.sub(r'[^A-Za-z0-9._-]', '_', pathlib.PurePosixPath(member).name) or 'file'
            stem, dot, ext = name.rpartition('.')
            candidate, n = name, 1
            while candidate.lower() in used:
                candidate = f'{stem}-{n}.{ext}' if dot else f'{name}-{n}'
                n += 1
            used.add(candidate.lower())
            target = destination / folder / candidate
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(member) as source, target.open('wb') as out:
                shutil.copyfileobj(source, out, 1024 * 1024)
            return target

        base, splits, packages = None, [], {}
        for member in apks:
            try:
                with zipfile.ZipFile(z.open(member)) as inner:
                    meta = _manifest(inner.read('AndroidManifest.xml'))
            except (zipfile.BadZipFile, KeyError, RuntimeError, RevivalError):
                continue  # Unreadable or encrypted APK: not part of the installable set.
            path = extract(member, 'apks')
            packages[path] = meta.get('package')
            if meta.get('split'):
                splits.append(path)
            elif base is None:
                base = path
            else:
                raise RevivalError('This bundle contains more than one base APK. Import a single app at a time.')
        if base is None:
            raise RevivalError('This bundle has split APKs but no base APK.' if splits else 'No readable APK was found inside this bundle.')
        package = packages[base]
        declared = None
        if 'manifest.json' in names:
            try:
                declared = json.loads(z.read('manifest.json')).get('package_name')
            except (ValueError, AttributeError):
                declared = None
        if declared and declared != package:
            raise RevivalError('The bundle description names a different app than its base APK.')
        splits = [s for s in splits if packages[s] == package]
        obb_paths = []
        for member in obbs:
            if package and package not in pathlib.PurePosixPath(member).name:
                continue
            obb_paths.append(extract(member, 'obbs'))
    return {'base': base, 'splits': splits, 'obbs': obb_paths, 'package': package}
