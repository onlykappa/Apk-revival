# V1 observed test results

Tested on 2026-10-12 in the build workspace. No user-supplied commercial APK was available. All Android artifacts in the demo are the self-authored Tap Quest fixture.

## Passing automated tests

**35 tests passed**, with no skips when both `APKR_TEST_APK` and `APKR_UI_TEST` were enabled. Standard tests run without Android SDK/Tk display and skip the explicitly optional integration tests.

| Coverage | Actual evidence |
|---|---|
| Original preservation | Copies hashed, mutation rejected, separate APK versions isolated |
| Input validation | Invalid executable, traversal, duplicate ZIP member, symbolic link, unsupported format and split version mismatch rejected |
| Analysis | Package/API/version, ABI and engine signatures, DEX/asset endpoint references, supplied log observations and conservative classification |
| Profile/plan safety | Exact hash/version preconditions, safe patch paths and unknown adapter rejection |
| Save privacy | Explicit input roles; private JSON/DAT excluded from portable asset export |
| Local protocol | Real loopback HTTP requests, 30 concurrent actions, level progression, restart persistence and unsupported actions rejected |
| Backend startup failure | Real occupied port rejected; starting after releasing it succeeds |
| Actual Android tools | Real compiled AXML/DEX fixture imported; both APK paths rebuilt, aligned, signed, signature-verified and exported |
| Export integrity | ZIP members rehashed; no private save files, signing keys or original APK included in game exports |
| Native desktop UI | Real Tk/Xvfb windows; library selection, evidence report and asynchronous plan rendering |
| Independent rebuild | Real button invoked; a coin collected, window closed/reopened, persisted coins loaded and incremented |
| Verification status gate | Every mandatory gameplay check required; host-only results and absent networking evidence cannot certify Android gameplay |
| Guest guard logic | Mocked command boundary verifies both IP families, cleanup, failure on absent IPv6, external-probe success rejection and nonce mismatch rejection |

Mocked guard tests validate application logic, **not actual guest firewall enforcement**. Real signing tests prove APK structure/signatures, **not gameplay**.

Commands:

```bash
APKR_TEST_APK="$PWD/build/tapquest-original.apk" APKR_UI_TEST=1 \
  python3 -m unittest discover -s tests -v
python3 scripts/demo.py --data build/final-demo-data --out build/final-demo-exports
```

The UI suite needs a working X DISPLAY. The separate fixture build used Android SDK Build Tools 35.0.0, Android platform 35, Eclipse compiler 3.39.0 and Java 17. Asset-only fixture patches preserved DEX and compiled resources and used zipalign/apksigner from the official SDK.

## Actual Android runtime attempt

A headless Android Emulator 37.2.12 with AOSP API 29 x86_64 was downloaded and booted using software acceleration because the workspace lacked KVM/Waydroid. Boot completed. The workbench's guest verification attempt then failed on an ADB timeout before any gameplay checks passed. The failure record has `passed=false` and `external_network_blocked=false`.

This does not establish that Waydroid launch/install works on a real Linux desktop or Steam Deck. The following remain unverified:

* Android cold launch and reaching meaningful gameplay.
* Android UI action, committed save and loading progress after relaunch.
* Actual Android-to-host backend reachability through ADB reverse.
* Actual guest IPv4/IPv6 enforcement and cleanup.
* Android recovery after backend startup/availability failure.
* Waydroid session behavior and Steam Deck controls/ARM translation.
* Any commercial game, missing server code or absent asset recovery.

Both Android demo exports are **Exported but Unverified**. The independent rebuild's GUI behavior was tested, but it cannot certify the original APK. No game in this release is marked Verified Offline.

## Artifacts

The source ZIP includes `demo/tapquest-original.apk`, `demo/offline_patch.zip`, `demo/local_backend.zip`, `demo/rebuild.zip`, a sanitized demonstration report and test output. Source control contains only fixture source and sanitized profile examples. The APKs and export packages are self-authored fixture artifacts, not proprietary games.

The portable rebuild can run immediately with Python/Tk. The original APK and APK exports require an Android runtime. Reproducing new signed exports additionally needs the documented SDK tools. Runtime verification should be completed on a configured Waydroid installation before making offline-play claims.
