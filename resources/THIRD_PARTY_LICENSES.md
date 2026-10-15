# Distribution licenses and source availability

APK Revival source and self-authored Tap Quest fixture: MIT, see project LICENSE.

The spatial focus scoring, focus-aware controller handling, job-stage design,
and launch-record patterns are adapted from OmniPC. Copyright (c) 2026 OmniPC
contributors. Its MIT license is included as OMNIPC-LICENSE.txt. Reference source:
https://github.com/onlykappa/OmniPC (src/renderer/lib/gamepad.ts, spatial.ts,
src/main/core/jobs.ts, src/main/launching/launchService.ts). OmniPC itself was
not modified.

PySide6 / Shiboken6 / Qt 6.8.3: this distribution uses the LGPL licensing option
for the dynamically loaded Qt modules. LGPL-3.0 and GPL-3.0 license texts are included. Qt libraries remain separate under
_internal/PySide6/Qt/lib and can be replaced with compatible modified builds.
The packaging specification and source are in the repository; there is no
signature enforcement or technical restriction preventing replacement.
Corresponding source and installation/build information:
https://download.qt.io/official_releases/qt/6.8/6.8.3/submodules/
https://download.qt.io/official_releases/QtForPython/pyside6/
https://code.qt.io/pyside/pyside-setup.git/tag/?h=v6.8.3
https://doc.qt.io/qtforpython-6/gettingstarted/package_details.html

SDL2: zlib license; SDL2-COPYRIGHT.txt retains the system distribution notice.
Source and build instructions: https://github.com/libsdl-org/SDL/tree/SDL2

PyInstaller: GPL licensing with the bootloader exception permitting packaged
applications; retain the bundled license notice. Source/build instructions:
https://github.com/pyinstaller/pyinstaller/tree/v6.12.0

Python 3.12: Python Software Foundation license. Source/license:
https://www.python.org/downloads/source/

System compatibility library notices are retained in LINUX-LIBRARY-NOTICES.txt. The package
uses the Linux dynamic loader and desktop system facilities. Ubuntu library
source packages are available at https://archive.ubuntu.com/ubuntu/pool/ .

Android SDK, apktool and Java are NOT included in this application package.
The optional in-app installer downloads verified upstream artifacts into the
user cache and retains their notices. Upstream licenses apply to those tools.
Temurin Java source/license: https://github.com/adoptium/temurin17-binaries
Android SDK licenses: https://developer.android.com/studio/terms
apktool source/license: https://github.com/iBotPeaches/Apktool

