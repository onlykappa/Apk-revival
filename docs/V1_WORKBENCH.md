# APK Revival V1

A local desktop workbench for investigating Android games, preparing reproducible restoration copies, managing an Android runtime, and exporting portable packages. **V1 is working software with a narrow adapter, not a universal APK converter.**

The supplied self-authored **Tap Quest** Android game intentionally depends on an unavailable backend. V1 supports three fixture workflows: select an existing offline gameplay branch in a signed APK; route the same client to a documented persistent local backend; or export an independent desktop rebuild. No commercial game restoration has been demonstrated.

## Start the desktop app

Linux / SteamOS Desktop Mode, Python 3.10+ with Tk:

```bash
git clone https://github.com/onlykappa/Apk-revival.git
cd Apk-revival
python3 -m apk_revival legacy-gui
```

No Python packages, account, API key, or cloud service is required for import, analysis, profiles, the backend, rebuild or desktop app. On Ubuntu/Debian, install `python3-tk` if Tk is missing. SteamOS dependencies must be configured separately; this project does not change the immutable system or install Waydroid for you.

For signing and fixture construction, install Java 17 (`java`, `keytool`) and Android SDK Build Tools / Platform Tools. Optional Linux x86_64 bootstrap downloads pinned tools into your user cache, without root installation:

```bash
python3 scripts/bootstrap_tools.py --fixture
source "$HOME/.cache/apk-revival/tools/env.sh"
python3 -m apk_revival doctor
python3 scripts/build_fixture.py \
  --android-jar "$HOME/.cache/apk-revival/tools/android-35/android.jar" \
  --ecj "$HOME/.cache/apk-revival/tools/ecj.jar"
python3 scripts/demo.py
```

Review upstream tool licenses before downloading. The source distribution contains no third-party tool binaries. Network is needed only to obtain setup dependencies. After setup, core operations are local. Asset-only patches preserve original compiled resources and DEX while rebuilding the APK archive; smali/XML operations use apktool and require additional framework support where appropriate.

## Desktop workflow

1. Import a base APK. Attach OBBs, splits, assets, logs or save files. Folder assets can be attached through the CLI.
2. Analyze. Read metadata, inventory, endpoint references, confidence, obstacles and the provisional recommended path.
3. Configure a Waydroid ADB serial. Inspect dependency/runtime checks and use Diagnostics to observe an original client.
4. Review the selected path's explicit JSON plan. Prepare it on a separate copy. V1 has a trusted Tap Quest adapter; unknown games stop at Needs Evidence.
5. Play or stop. The launcher installs the prepared client, coordinates its backend and checks guest-to-host reachability. Save backups remain private and local.
6. Verify offline. V1's fixture verifier enforces temporary guest-wide IPv4/IPv6 restrictions and checks actual gameplay, progress persistence and backend recovery. It refuses to certify an unavailable/unsupported environment.
7. Export. Signed APK bundles, local backend bundles and independent rebuild packages are separate outputs. Exports include a profile, evidence report, file hashes, launcher and instructions. They exclude original APKs, private saves, logs and signing keys.

Re-signed APKs generally cannot update an installed original with another signature. The launcher reports Android's error and never silently uninstalls an app or deletes its data.

## Connect Waydroid

Initialize Waydroid separately on a compatible Linux host. Start its session and find the guest IP in Android Settings > About:

```bash
adb connect GUEST_IP:5555
python3 -m apk_revival list
python3 -m apk_revival runtime GAME_ID --serial GUEST_IP:5555
python3 -m apk_revival play GAME_ID
```

Keep the CLI launcher running while playing; Ctrl+C stops the game, local forwarding and backend. The GUI manages this lifecycle directly. An ADB serial is mandatory to prevent installing on an unintended device. Runtime API and ABI checks fail with actionable errors. ARM translation on x86/Steam Deck is a separate runtime configuration task.

A custom launcher manages Android; it does not replace Android. Other runtimes can implement the adapter boundary in `runtime.py`. V1's first target is Waydroid; device-specific integration still needs hardware validation.

## Commands

```bash
python3 -m apk_revival import game.apk --support main.1.game.obb --logs launch.log --assets asset-folder --saves clean-save.json
python3 -m apk_revival analyze GAME_ID
python3 -m apk_revival report GAME_ID
python3 -m apk_revival plan GAME_ID offline_patch
python3 -m apk_revival prepare GAME_ID offline_patch
python3 -m apk_revival diagnostics GAME_ID --original
python3 -m apk_revival verify GAME_ID
python3 -m apk_revival backup GAME_ID
python3 -m apk_revival restore GAME_ID backup.zip
python3 -m apk_revival export GAME_ID portable.zip
```

File roles can be explicit with `--assets`, `--logs` and `--saves` on import/attach. Unknown JSON/XML attachments are evidence and are not exported automatically. DAT/BIN files default to saves; mark actual game assets explicitly. Asset folders retain relative paths.

Use `--data /absolute/private/location` before the command to change the private local data root. Defaults to `~/.local/share/apk-revival`, outside the repository. `reset` resets the current restoration selection but preserves prior work and profile history for review. An exact hash/version-bound custom patch plan can be supplied through `prepare ... --plan reviewed.json`. Imported profiles never execute arbitrary code.

## Tests and demonstration

```bash
python3 -m unittest discover -s tests -v
APKR_TEST_APK="$PWD/build/tapquest-original.apk" python3 -m unittest discover -s tests -v
```

The optional integration test invokes actual Android signing/alignment tools for both APK restoration paths. Default structural tests use non-runnable test ZIPs and never claim Android gameplay. The demo builds exports from a real self-authored APK and tests host backend persistence. See [TEST_RESULTS.md](docs/TEST_RESULTS.md) for the exact observed results and unverified items, [FIXTURE.md](docs/FIXTURE.md) for the test game protocol, and [VERIFICATION.md](docs/VERIFICATION.md) for the offline gate and recovery commands.

## What V1 can and cannot do

| Capability | V1 status |
|---|---|
| Native desktop library, import, reports, profiles, progress/logs, export | Implemented |
| APK AXML/DEX metadata and reference inspection | Implemented; bounded static analysis |
| OBB, separate split, asset/log/save import | Implemented; arbitrary placement is not invented |
| Exact asset/text patches, rebuild/alignment/signature verification | Implemented; actual asset fixture tested |
| Persistent local server with Android reachability probe | Implemented for Tap Quest; guest behavior requires runtime validation |
| Separate rebuild | Implemented for Tap Quest; independent gameplay is not original APK restoration |
| Waydroid launcher and guest offline gameplay verifier | Implemented; runtime/hardware execution status in test report |
| Generic gameplay reconstruction, arbitrary server emulation, missing asset recovery | Not implemented |
| Patching or re-signing split sets | Not implemented; split inspection/install boundary only |
| Automatic backup of unknown games' private data | Not implemented; adapter-specific locations required |
| Exhaustive engine identification/native decompilation | Not implemented; signatures and evidence leads only |

Static endpoint references do not establish request/response semantics. Server-owned logic, missing assets, obfuscated native code, signature checks, authentication services or runtime incompatibility can make restoration impractical. A rebuild starts with an independent feasibility assessment and progress record.

## First real game: files to supply

* The exact base `.apk`, game title, version and where it stops during a cold launch.
* Every matching split `.apk`, expansion `.obb`, and any legitimately available downloaded asset/cache folder. Extract XAPK/APKS bundles first; V1 rejects those containers explicitly.
* A launch/crash `logcat` capture if available, plus screenshots of the failure and a description of a meaningful gameplay action.
* Any available source, documented protocols or request/response examples. Redact accounts, credentials and tokens before sharing.
* An optional save you want preserved, its original device/runtime, and known save location. A clean test save is preferable.
* The target device and runtime details: Steam Deck/PC, Waydroid Android version, guest ABIs and whether ARM translation is configured.

No signing keys, accounts, purchase credentials or API key are required to start analysis. User files remain outside source control. Only restore and redistribute material for which you have the necessary rights.

## Repository publishing

If the supplied repository is not accessible through the GitHub app, use the source archive and [PUBLISHING.md](docs/PUBLISHING.md). This does not block local operation.

MIT license covers this project's source and self-authored fixture. Android SDK, apktool and Eclipse compiler retain their own licenses.

