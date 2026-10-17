# Linux x86_64 one-directory distribution with replaceable Qt libraries (LGPL).
from pathlib import Path
import ctypes.util
import os
from PyInstaller.utils.hooks import collect_data_files
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
# Game plugins (core subpackages with a plugin.py, e.g. meego) are published as
# separate plugin files and are left out of the app download.
plugin_dirs=[p.parent for p in (root/'apk_revival').glob('*/plugin.py')]
def core_file(p):return not any(d in p.parents for d in plugin_dirs)
plugin_resources={'meego-starter.json'}
assets=[(str(p),'resources') for p in (root/'resources').iterdir() if p.is_file() and p.name not in plugin_resources]+collect_data_files('certifi')
assets += [(str(p), str(p.relative_to(root).parent)) for p in (root/'apk_revival').rglob('*.py') if core_file(p)]
# Standard-library modules that installed plugins may import, kept even when the core does not use them.
plugin_stdlib=['argparse','base64','copy','hashlib','hmac','http.server','io','itertools','json','math','plistlib','secrets','struct','tempfile','types','urllib.parse','uuid','zipfile']
a=Analysis([str(root/'packaging/entry.py')],pathex=[str(root)],binaries=extra,datas=assets,hiddenimports=['PySide6.QtSvg']+plugin_stdlib,hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['apk_revival.'+d.name for d in plugin_dirs]+['PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtQml','PySide6.QtQuick','PySide6.QtTest','tkinter','pytest','numpy'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='APK-Revival',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='APK-Revival')


