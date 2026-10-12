# Quick start for the source package

Unzip `APK-Revival-v1-source.zip`. Open a terminal in the `Apk-revival` folder.

## Desktop workbench

```bash
python3 -m apk_revival gui
```

Python 3.10+ and Tk are required. Import the included `demo/tapquest-original.apk`, then Analyze. This is a deliberately server-dependent self-authored fixture. Plan/prepare produces separate artifacts; it never changes the original.

## Play the separate rebuild now

No Android SDK or Waydroid is needed:

```bash
python3 -m zipfile -e demo/rebuild.zip demo/rebuild
python3 demo/rebuild/run.py
```

Collect coins, close the window, and reopen it. Progress persists. This is an independently implemented desktop version of the fixture, not a patched original APK.

## Run the Android exports

Configure Waydroid independently and connect its exact ADB serial first. Then:

```bash
python3 -m zipfile -e demo/offline_patch.zip demo/offline_patch
python3 demo/offline_patch/run.py --serial GUEST_IP:5555
```

Or use the local backend package:

```bash
python3 -m zipfile -e demo/local_backend.zip demo/local_backend
python3 demo/local_backend/run.py --serial GUEST_IP:5555
```

The backend launcher must remain open while playing. Ctrl+C stops it. Android-to-host communication is probed before launch. Neither provided APK export is labeled Verified Offline because guest gameplay verification did not pass in the build environment.

For generating fresh restoration artifacts and running offline verification in the main workbench, follow README.md's tool setup and Waydroid configuration. For your first actual game, supply the exact base APK and all matching supporting files listed in the README.
