#!/usr/bin/env python3
"""Validated version/notes and source/checksum assets for GitHub release CI."""
import hashlib,pathlib,re,subprocess,tomllib,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]

def version(root=ROOT):
    value=tomllib.loads((root/'pyproject.toml').read_text())['project']['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+',value):raise ValueError('Expected a semantic release version')
    engine=(root/'apk_revival/__init__.py').read_text()
    if not re.search(r'__version__\s*=\s*[\"\']'+re.escape(value)+r'[\"\']',engine):raise ValueError('Engine and project versions differ')
    return value

def notes(value,root=ROOT):
    text=(root/'CHANGELOG.md').read_text();match=re.search(r'^## \['+re.escape(value)+r'\][^\n]*\n(.*?)(?=^## |^\[\d|\Z)',text,re.M|re.S)
    if not match or not match.group(1).strip():raise ValueError('Missing release notes for '+value)
    return match.group(1).strip()+'\n'

def build_assets(root=ROOT):
    value=version(root);dist=root/'dist';dist.mkdir(exist_ok=True)
    binary=dist/'APK-Revival-v2-linux-x86_64.tar.gz'
    if not binary.is_file():raise ValueError('Build and smoke-test the Linux application first')
    package=dist/('APK-Revival-'+value+'-linux-x86_64.tar.gz');binary.rename(package)
    source=dist/('APK-Revival-'+value+'-source.zip')
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for name in subprocess.check_output(['git','ls-files'],cwd=root,text=True).splitlines():z.write(root/name,'APK-Revival/'+name)
        z.write(root/'resources/tapquest-original.apk','APK-Revival/resources/tapquest-original.apk')
    (dist/'RELEASE-NOTES.md').write_text(notes(value,root))
    (dist/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in [package,source]))
    return value

if __name__=='__main__':print(build_assets())

