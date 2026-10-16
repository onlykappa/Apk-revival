# APK opener test record — 2026-10-13

Local build: 0.3.8. Real device files: Steam Deck, existing SteamOS Waydroid main image and restored Meego profile `030613cbc63bd03786545999`.

| Check | Result | Evidence / limit |
|---|---|---|
| New opener and Steam safeguards | PASS, 15 tests | `evidence/opener-tests.txt`; runtime command boundaries use test doubles |
| Actual Qt import, queued imports, Play/Stop controls | PASS, 3 tests | `evidence/ui-tests.txt`; Android launch boundary uses a test double |
| Full source suite | 97 PASS, 15 SKIP, 6 BLOCKED errors | 118 total; all six errors are socket creation denied by the sandbox; `evidence/source-suite.txt` |
| Packaged file-open IPC | PASS | Two real packaged processes; the second import appears in the existing window; `evidence/packaged-ipc.txt` |
| Packaged and installed UI smoke | PASS | Offscreen window opens/closes, packaged import shows Play; `evidence/packaged-library.png`, `packaged-smoke.txt`, `installed-smoke.txt` |
| Real Meego APK metadata | PASS | aapt reads `ata.fresh.meego`, `com.apportable.activity.VerdeActivity`, `armeabi`, raster icon |
| Existing prepared Meego artifact identity | PASS | REA archive inspection and SHA-256 match; `evidence/rea-restored-apk.json` |
| Real launch from stopped runtime | BLOCKED | Managed supervisor reaches `waydroid-mount`; sudo rejects the sandbox's `NoNewPrivs=1`; `evidence/meego-launch.txt` |
| Second real Android launch | BLOCKED | First Android startup cannot run in this environment; repeated command-boundary launch behavior is covered by unit/UI tests |
| Recovery after a real reboot | BLOCKED | No access to host reboot/services; no reboot performed |
| Retained host Meego save, profile and prepared artifact | PASS, unchanged hashes | Before/after hashes in `evidence/meego-before.json` and `evidence/meego-after.json`; no reset, uninstall or save deletion |
| Retained Android gameplay progress | UNVERIFIED | Android data directories exist, but host runtime/private data cannot be inspected or exercised here |
| Gaming Mode rendering/controller handoff | UNVERIFIED | Needs launch in host Gaming Mode |
| Dolphin APK association and Gaming launcher installation | PASS, files verified | Desktop Exec uses `%F`, MIME defaults point to APK Revival, Gaming script executable; actual host Dolphin/Gaming windows are unverified |
| Steam library registration on the actual host | PENDING | Gaming launcher supplied; close Steam and select Setup > Add to Steam to register safely |

The sandbox also denies system D-Bus access and local TCP sockets. It exposes no `/dev/kvm` or Binder devices to this process. Missing devices inside this sandbox do not establish that the Deck's host installation is broken. `waydroid status` reports uninitialized while the SteamOS image is unmounted; the launcher uses the existing mount helper rather than initializing Android.

The restored game is not replaced with the separate `ata.fresh.meego` APK used for metadata inspection. Its prepared `ata.apkrv.meego` package, backend rules and host village save remain selected by the restoration workflow. No Android image, application data or save files were reset/deleted.

To finish real testing outside the agent sandbox, use the normal desktop shortcut: stop the runtime through its existing host controls, press Play on the existing restored Meego entry, observe the game and its saved village, stop/play again, then reboot the Deck and repeat. Record the visible village/progress before and after. These remaining checks cannot be claimed from mock tests or process presence.
