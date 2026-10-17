# APK Revival: managed APK opener

This is a local candidate build for this Steam Deck. The APK import UI, launcher safeguards and host-service tests are recorded in [OVERNIGHT_HANDOFF.md](history/OVERNIGHT_HANDOFF.md). Live Android, cold-start, reboot and physical input results have separate pass/block status; a host test or successful activity launch alone does not certify gameplay. Privileged startup can still require a graphical authorization prompt.

## Use

Open APK Revival from the desktop or application menu. Choose **Add game > Browse**, select an APK, then press **Play**. Dropping an APK into the library or opening it from Dolphin also imports it. The library keeps its own unchanged original copy.

Play opens an ordinary APK without requiring a restoration adapter. It automatically starts the existing Android runtime, waits for readiness, discovers its current IP, connects ADB, installs the APK if necessary and resolves its enabled MAIN/LAUNCHER activity. Startup authorization, if needed, uses a graphical password prompt. No terminal, IP lookup or manual ADB connection is part of this workflow.

For a game that already has a prepared restoration, Play keeps using that signed artifact, its existing package, local responder and save directory. **Prepare game** remains available for supported restoration adapters. Launching an original APK does not repair unavailable servers or certify offline gameplay.

## Dependencies

APK Revival manages **Waydroid**; it does not replace Android. This Deck's existing `~/Android_Waydroid/waydroid.img`, main profile, installed SteamOS mount/service helpers and verified Cage bundle are required. The Android SDK connection and inspection tools are already in `~/.cache/apk-revival/tools/` on this Deck. Setup can install preparation/connection tools on other installations. The package includes Python and Qt; no Python installation is needed to open it.

Do not initialize or reset Android to use this build. It uses the installed main profile and checks ownership before mounting. It does not switch to the test profile. SteamOS/kernel updates can still require repair of the separate Waydroid host integration.

## Desktop and Gaming Mode

Installation creates an application-menu shortcut and updates the APK file association for Dolphin. File paths containing spaces are passed as arguments. When APK Revival is already open, another Dolphin invocation queues its APK import in the existing window.

A Gaming Mode launcher is installed at `~/.local/bin/apk-revival-gaming`. To register the Steam library entry, close Steam, open APK Revival, and choose **Setup > Add to Steam**. The registration preserves other binary shortcut records and makes a backup. Steam must be closed because it can overwrite its shortcut file when it exits. Registration was left pending during the sandbox installation because the host Steam process state cannot be verified here.

The Steam entry opens the full library with `--fullscreen`. Browse with the D-pad/trackpad; game controls depend on the Android game and the existing runtime controller integration. Gaming Mode display/input behavior remains unverified in this session.

## Local automation controls

For development and unattended checks, the executable accepts `--play GAME_ID`, `--stop-game`, `--restart-runtime` and `--quit`. These queue private, expiring requests in the same data directory and use the normal window's worker, runtime ownership, authorization and cleanup. They do not require another launcher process to own Android. The printed JSON identifies a result file whose final state is `succeeded` or `failed`; queuing a request is not a passed test. Stop the game before requesting a runtime restart. Routine use remains the library's Play button.

## Save protection and failures

- APK installation uses replacement installation (`-r`), never uninstall, clear-data, downgrade or signature bypass. A different signing key or a newer installed version produces an explanation and preserves the installed copy.
- An identical guest APK hash skips installation. Changed prepared artifacts produce a repair error rather than silently launching the original.
- Restored Meego continues to use `games/030613cbc63bd03786545999/saves/village.json` and its prepared backend data. Other Meego packages in Android are not removed or migrated.
- Architecture checks compare APK native ABIs with Android's advertised supported ABIs. Legacy `armeabi` can use an advertised `armeabi-v7a` runtime. Missing ARM support is reported; this build does not install or assume working translation.
- Android API mismatches, missing splits, signature conflicts, insufficient storage, rejected activities and immediate crashes produce specific errors. Adaptive/vector icons use fallback artwork when a raster icon is unavailable.
- Readiness polling is bounded: the SteamOS startup stage allows 110 seconds plus bounded status/ADB commands; boot/package-manager readiness allows 45 seconds. Commands have individual timeouts. Activity start allows 30 seconds, with up to 8 seconds of process checks. Install allows 180 seconds. Readiness polls retry discovery; failures never trigger a runtime reset or repeated destructive installation.
- Native crash excerpts are diagnostic leads. An activity/process check is not proof that a game renders or retains progress.

## Runtime alternatives investigated

Android Emulator can replace Waydroid, but still needs an Android system image and a virtual device with separate storage. It is not a drop-in way to keep this Deck's restored installation. Its GPU, ARM compatibility and controller behavior with this game were not tested. See [Android Emulator documentation](https://developer.android.com/studio/run/emulator).

[Cuttlefish](https://source.android.com/docs/devices/cuttlefish) is another virtual Android device intended for platform/framework testing. It also requires a runtime and Android images. There is no tested migration of this installation to it.

[Anbox](https://github.com/anbox/anbox) is archived and describes itself as another full Android container. It is not a suitable new dependency here.

The practical choice for this task is to manage the already installed Waydroid system behind APK Revival. This conclusion concerns this Deck and save-preserving workflow; it is not a claim that Waydroid is the only possible Android runtime.

## Implementation evidence

The source snapshot comes from `onlykappa/Apk-revival`, upstream commit `df989d14740d4068b47ce7cafb4f89a1d1aebfdc`, fetched through the GitHub connector because shell DNS was unavailable.

Installed Waydroid source inspected: `tools/actions/status.py` reports the current guest IP through its network helper; `app_manager.py` exposes sessions/apps and the `waydroid.active_apps` display property. Its app-install command logs some failures without reliable shell exit semantics, so the launcher uses ADB's install result and Android package-manager activity resolution for confirmation. See [Waydroid CLI documentation](https://docs.waydro.id/usage/waydroid-command-line-options) and [app installation documentation](https://docs.waydro.id/usage/install-and-run-android-applications).

REA archive inspection confirmed the prepared APK identity (`5b00554d…48ebaee`), with Evidence ID `ev_ba0be4cec9212f5368b8ad766945deb35fb6a9f910aa25073fcb071c8180d87a`. Its archive inventory is static; it does not verify gameplay or signatures. REA Android decompilation was unavailable because its JADX MCP JAR was not configured. SDK aapt and the project's manifest parser supplied package/activity/icon/ABI evidence instead.

## Build and rollback

Normal contributor builds use `scripts/package_linux.py` and `packaging/apk-revival.spec`. This offline build reused the installed licensed PyInstaller bootloader and dependencies, replacing all project modules from source with `scripts/repack_installed.py` under CPython 3.12. It does not require that build interpreter at runtime. Framework/license notices remain in `_internal/resources`.

The previous installed application was preserved in a timestamped `~/.local/share/apk-revival-app.previous-*` directory; the older `.previous` backup is also retained. A rollback changes the executable/application directory and shortcuts, not `~/.local/share/apk-revival` or Android data. See `TEST_RESULTS_OPENER.md` for exact pass/block status.
