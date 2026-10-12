# V2 observed test results

Build date: 2026-10-12. Linux x86_64, Python 3.12, PySide6 6.8.3. No physical Steam Deck or running compatible Waydroid guest was available.

## Automated suite

49 tests ran: 47 passed, 2 optional legacy Tk display tests skipped. Actual Android SDK signing/alignment integration and the three native Qt interface workflow tests were enabled. The V1 tests remain included.

Real Qt widgets were exercised using QtTest: Add Game, analysis, signed offline preparation, honest missing-runtime status, path selection, separate rebuild preparation, Play, collect, Stop, relaunch, save backup, reversible restore and export. Modal file selection for backup/export was supplied by a test double; the operations, files and persistence were real. Controller confirm/back and spatial focus were dispatched programmatically, not through a physical controller.

Service tests cover unknown-game readiness, failure/cancellation stages, multiple-device selection, safe argument boundaries, actual save backup/restore, private diagnostics, exports, installer rollback copies and cached installation decisions. Android command/discovery tests use doubles and do not establish guest behavior. Native export filesystem tests additionally check hashes and exclusion of private saves and the unrelated fixture APK.

## Real additional checks

* Built the self-authored executable Android fixture from Java source and exercised both signed APK paths using actual Android tools. Signatures and ZIP alignment passed; these are not Android gameplay checks.
* Downloaded, checksum-verified and installed a private Temurin 17 runtime plus the pinned preparation tools in an isolated user directory. Executables and preparation readiness passed.
* Built the one-directory Linux application and started it using Qt offscreen and XCB under Xvfb at 1280 × 800.
* Exported the actual native application with the separate Tap Quest rebuild, checked every package hash, opened its single-game Qt interface, collected a coin and confirmed progress after stop/relaunch. This verifies the separate desktop implementation only.
* V1 backend tests exercise actual local HTTP requests, persistence, concurrent actions, rejected unsupported operations and startup failure/recovery.

## Unverified

No V2 gameplay check ran on actual Android. V1's earlier emulator attempt timed out before Android gameplay verification. Cold launch, meaningful original gameplay, Android saves/relaunch, guest-to-host backend reachability and guest external-network blocking therefore remain unverified. No fixture was marked Verified Offline.

Physical gamepad/touch hardware, Steam Gaming Mode, SteamOS-specific Waydroid installation, ARM translation and private save permissions require target-device testing. No commercial game restoration was demonstrated. Unknown games require evidence and a trusted game-specific adapter.

The two optional Tk tests were previously exercised during V1; V2's automated suite focuses on the new Qt launcher. GitHub Actions results must be read from the actual published workflow run and are not assumed from these local results.
