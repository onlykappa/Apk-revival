# Development and packaging

Python 3.10+ supports the engine. The distributed Linux x86_64 build uses Python 3.12, PySide6 6.8.3, PyInstaller 6.12.0 and Ubuntu 24.04 (glibc 2.39). Build on an older compatible base to target older systems. User installation requires neither Python nor a terminal.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[launcher,build]'
python scripts/bootstrap_tools.py --fixture
source "$HOME/.cache/apk-revival/tools/env.sh"
python scripts/build_fixture.py --android-jar "$HOME/.cache/apk-revival/tools/android-35/android.jar" --ecj "$HOME/.cache/apk-revival/tools/ecj.jar"
cp build/tapquest-original.apk resources/tapquest-original.apk
python -m apk_revival gui
```

The self-authored fixture APK is built from repository source and ignored by Git. Never add user APKs, assets, private saves or signing keys to the repository.

```bash
QT_QPA_PLATFORM=offscreen APKR_V2_UI_TEST=1 APKR_TEST_APK="$PWD/build/tapquest-original.apk" python -m unittest discover -s tests -v
python scripts/package_linux.py
QT_QPA_PLATFORM=offscreen dist/APK-Revival/APK-Revival --smoke --data "$PWD/build/package-smoke"
```

Linux packaging needs SDL2 and Qt's XCB dependencies on the build host. CI installs `libsdl2-2.0-0` and `libxcb-cursor0`; PyInstaller gathers shared libraries. An optional `APKR_PACKAGE_LIBS` directory supplies additional regular `libxcb-*.so.*` files when building without host package installation. Keep their copyright notices. Qt libraries remain external and replaceable for LGPL compliance. See `resources/THIRD_PARTY_LICENSES.md`.

The CI package is attached to the native-launcher workflow run as an artifact. CI tests are not Android gameplay verification. Use the runtime-specific offline verifier on a compatible guest and record its evidence before claiming Verified Offline.

Publishing uses the Release workflow; see [RELEASES.md](RELEASES.md). EGL and the full XCB dependency set must be present on the build host. The release runner checks actual XCB startup before publishing.

