#!/usr/bin/env python3
"""Build a double-click Linux launcher. Contributor tooling, not a user step."""
import pathlib,subprocess,sys,tarfile,shutil
root=pathlib.Path(__file__).resolve().parents[1]
if not (root/'resources/tapquest-original.apk').exists():raise SystemExit('Build the self-authored fixture first, then copy it to resources/tapquest-original.apk')
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','packaging/apk-revival.spec'],cwd=root,check=True)
app=root/'dist/APK-Revival'
shutil.copyfile(root/'docs/INSTALL_V2.md',app/'START-HERE.txt')
out=root/'dist/APK-Revival-v2-linux-x86_64.tar.gz'
with tarfile.open(out,'w:gz',compresslevel=6) as tar:tar.add(app,arcname='APK-Revival')
print(out)
