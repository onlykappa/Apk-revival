#!/usr/bin/env python3
"""Optional Linux tooling download with pinned SHA-256 checks. No root writes."""
import argparse,hashlib,os,pathlib,shlex,urllib.request,zipfile
ITEMS={
 'buildtools.zip':('https://dl.google.com/android/repository/build-tools_r35_linux.zip','bd3a4966912eb8b30ed0d00b0cda6b6543b949d5ffe00bea54c04c81e1561d88'),
 'platformtools.zip':('https://dl.google.com/android/repository/platform-tools_r37.0.1-linux.zip','d230f13842f60f782a8645f9c813f8f845bf36089ea7289f28c48f17979313f1'),
 'apktool.jar':('https://github.com/iBotPeaches/Apktool/releases/download/v2.12.1/apktool_2.12.1.jar','66cf4524a4a45a7f56567d08b2c9b6ec237bcdd78cee69fd4a59c8a0243aeafa'),
 'platform.zip':('https://dl.google.com/android/repository/platform-35_r02.zip','0988cacad01b38a18a47bac14a0695f246bc76c1b06c0eeb8eb0dc825ab0c8e0'),
 'ecj.jar':('https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.39.0/ecj-3.39.0.jar','01f5a92ac19bb2b3bf85e295a68f2c73c264369109158b566ce9b490af982948')}
p=argparse.ArgumentParser(description='Download official SDK/build tools and apktool for Linux x86_64. Requires Java 17 and acceptance of upstream licenses.');p.add_argument('--directory',default=str(pathlib.Path.home()/'.cache/apk-revival/tools'));p.add_argument('--fixture',action='store_true');a=p.parse_args();root=pathlib.Path(a.directory).expanduser().resolve();root.mkdir(parents=True,exist_ok=True)
for name,(url,sha) in ITEMS.items():
    if not a.fixture and name in ['platform.zip','ecj.jar']:continue
    target=root/name
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=sha:
        print('Downloading',name,flush=True);urllib.request.urlretrieve(url,target)
    if hashlib.sha256(target.read_bytes()).hexdigest()!=sha:raise SystemExit('Checksum mismatch: '+name+'. Download refused; check upstream before updating a pin.')
    if name.endswith('.zip'):
        with zipfile.ZipFile(target) as z:
            for i in z.infolist():
                f=pathlib.PurePosixPath(i.filename)
                if f.is_absolute() or '..' in f.parts:raise SystemExit('Unsafe upstream archive')
            z.extractall(root)
for name in ['aapt','aapt2','d8','apksigner','zipalign']:(root/'android-15'/name).chmod(0o755)
(root/'platform-tools/adb').chmod(0o755)
env={**{f'APKR_{n.upper()}':str(root/'android-15'/n) for n in ['aapt','d8','apksigner','zipalign']},'APKR_ADB':str(root/'platform-tools/adb'),'APKR_APKTOOL_JAR':str(root/'apktool.jar')}
(root/'env.sh').write_text('\n'.join('export '+k+'='+shlex.quote(v) for k,v in env.items())+'\n')
print('Next: source '+shlex.quote(str(root/'env.sh')))
if a.fixture:print('Fixture build: python3 scripts/build_fixture.py --android-jar '+shlex.quote(str(root/'android-35/android.jar'))+' --ecj '+shlex.quote(str(root/'ecj.jar')))

