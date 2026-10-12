# Linux x86_64 one-directory distribution with replaceable Qt libraries (LGPL).
from pathlib import Path
import ctypes.util
import os
root=Path(SPECPATH).parent
sdl=ctypes.util.find_library('SDL2-2.0')
extra=[]
if sdl:
    for parent in [Path('/usr/lib/x86_64-linux-gnu'),Path('/lib/x86_64-linux-gnu')]:
        candidate=parent/sdl
        if candidate.exists():extra=[(str(candidate.resolve()),'.')];break
extra_dir=os.environ.get('APKR_PACKAGE_LIBS')
if extra_dir:
    for p in Path(extra_dir).glob('libxcb-*.so.*'):
        if p.is_file() and not p.is_symlink():extra.append((str(p),'.'))
assets=[(str(root/'resources'),'resources')]
a=Analysis([str(root/'packaging/entry.py')],pathex=[str(root)],binaries=extra,datas=assets,hiddenimports=['PySide6.QtSvg'],hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtQml','PySide6.QtQuick','PySide6.QtTest','tkinter','pytest','numpy'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='APK-Revival',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='APK-Revival')
