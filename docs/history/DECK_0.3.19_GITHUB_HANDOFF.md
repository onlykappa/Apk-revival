# APK Revival 0.3.19 GitHub handoff

Published branch: [deck-0.3.19-meego](https://github.com/onlykappa/Apk-revival/tree/deck-0.3.19-meego).

Published commit: [b2e07a353a111b4b3ca8fd3c195c69511d34fbc4](https://github.com/onlykappa/Apk-revival/commit/b2e07a353a111b4b3ca8fd3c195c69511d34fbc4).

Exact message: `Deck 0.3.19 local changes (ChatGPT Meego adjustments)`.

Sole parent: `df989d14740d4068b47ce7cafb4f89a1d1aebfdc` (official 0.3.7).

Source: `/home/deck/Apk-revival/apk_revival/__init__.py` reports 0.3.19.
Fresh review clone: `/tmp/apk-revival-deck-0.3.19-20261015`.

## Scope and verification

- 75 changed files: 25 additions and 50 modifications; 3,990 insertions and 229 deletions.
- Copied 76 eligible source/resource files, byte-verified; one logo was already identical to the base.
- 30 changed files differ only by trailing blank lines/newlines. Copied source formatting was retained, so baseline diff whitespace checks report those pre-existing extra EOF blank lines.
- No APK/OBB, keystore, signing material, save, log or cache was transferred. Even the self-authored resources/tapquest-original.apk fixture was excluded.
- No installed app, Android package or personal data was modified in this continuation.
- Direct shell git clone failed DNS. The authenticated GitHub connection retrieved the exact base commit/trees/blobs; each Git object SHA was verified, then a fresh shallow clone was created. GitHub Git-data tools transferred the commit tree and branch. The resulting remote commit has the required message, exact parent and byte-identical tree; the local review branch now tracks that same remote commit.
- Local source tests: 371 cases run, 362 passed, 9 skipped after excluding unavailable socket/Qt modules. The 118 focused gameplay cases are included in that count. Initial unfiltered discovery had sandbox socket errors, missing PySide6 and a release-note assertion; the local release-note failure was repaired.
- Both source and exported Python syntax passed; all exported runtime shell scripts passed bash -n. The temporary clone is clean. No new live-game, reboot, touch or physical latency test is claimed.

## Merge limitations

Only apk_revival/ and resources/ were exported as requested. Root tests, packaging configuration and release notes remain at df989d1. The exported pyproject.toml is therefore still 0.3.7 while the Python package reports 0.3.19; reconcile version metadata/release notes and bring over regression tests before packaging. No public release or merge was performed.

This is not complete original-game parity. Commercial reward collection, solo treasure/quest/dungeon systems and some scripted item paths remain missing. Native validation of the final-pickup candidate is still needed. See [offline status](https://github.com/onlykappa/Apk-revival/blob/deck-0.3.19-meego/apk_revival/meego/OFFLINE_STATUS.md).

## Every changed file

| Status | File | Change |
| --- | --- | --- |
| M | `apk_revival/__init__.py` | Reports package version 0.3.19. |
| M | `apk_revival/__main__.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `apk_revival/adapters.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `apk_revival/analysis.py` | Optionally preserves binary manifest closing events to identify the actual launcher intent filter. |
| M | `apk_revival/backend.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `apk_revival/cli.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `apk_revival/exporter.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `apk_revival/launcher/__init__.py` | Trailing blank line/newline only; logic/content unchanged. |
| A | `apk_revival/launcher/apk_info.py` | Reads package, launcher activity, architecture, SDK levels, title and icon through aapt, with direct manifest fallback. |
| A | `apk_revival/launcher/connection_recovery.py` | Bounds recovery of the owned ADB device/reverse connection and verifies the current local-service health nonce. |
| M | `apk_revival/launcher/controller.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `apk_revival/launcher/entry.py` | Accepts Dolphin APK paths, queues requests to the existing instance, and adds bounded library-control and diagnostic entry points. |
| A | `apk_revival/launcher/input_diagnostics.py` | Captures bounded input, focus, display and rendering diagnostics with explicit coverage limits. |
| M | `apk_revival/launcher/install.py` | Registers APK file association, Gaming Mode wrapper and Steam shortcut; preserves previous installations and MIME settings. |
| M | `apk_revival/launcher/jobs.py` | Persists completed job outcomes and reports history-write failures without losing the task result. |
| M | `apk_revival/launcher/meego_test.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `apk_revival/launcher/network.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `apk_revival/launcher/portable.py` | Gives portable Meego services their selected APK for original-rule/catalog loading. |
| M | `apk_revival/launcher/presentation.py` | Makes direct APK Play available independently of restoration-adapter support. |
| A | `apk_revival/launcher/requests.py` | Validates and bounds private queued Play/Stop/restart/quit and Dolphin import requests. |
| M | `apk_revival/launcher/runtime_setup.py` | Manages existing SteamOS runtime startup/readiness, display environment, authorization, current ADB discovery and owned-session recovery/cleanup. |
| M | `apk_revival/launcher/service.py` | Connects APK analysis and direct Play, camera revision preparation, job logs, connection recovery, diagnostics and preserved fresh-village backups. |
| A | `apk_revival/launcher/steam.py` | Registers a non-Steam shortcut with backups and safe handling of Steam shortcut data. |
| M | `apk_revival/launcher/style.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `apk_revival/launcher/tools_setup.py` | Configures the available SDK aapt executable used for APK metadata. |
| M | `apk_revival/launcher/ui.py` | Wires direct Play, APK icons, file/drop imports, runtime/input controls and asynchronous status updates into the existing design. |
| M | `apk_revival/launcher/updater.py` | Trailing blank line/newline only; logic/content unchanged. |
| A | `apk_revival/meego/OFFLINE_STATUS.md` | Records implemented source behavior, local reconstruction policies, actual tests, remaining core gaps and export packaging limitations. |
| M | `apk_revival/meego/__init__.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `apk_revival/meego/adapter.py` | Includes reviewed camera/timer patches and extracts original birthstone/progression/dungeon rule sections during preparation. |
| M | `apk_revival/meego/backend.py` | Loads original catalog and additional rules for already prepared clients without rewriting their prepared data files. |
| A | `apk_revival/meego/camera.py` | Guards the exact native move-gate repair by original hash/instruction bytes and tracks prepared client revisions. |
| M | `apk_revival/meego/engine/__init__.py` | Trailing blank line/newline only; logic/content unchanged. |
| A | `apk_revival/meego/engine/birthstones.py` | Loads and validates all original birthstones, populates native catalog metadata, and discovers actually owned stones. |
| A | `apk_revival/meego/engine/catalog.py` | Restores original-price catalog purchases, tool research/unlocks and compatible research cursor encoding. |
| A | `apk_revival/meego/engine/community.py` | Schedules bounded permanent local arrivals with housing checks and persistent retry-safe metadata. |
| A | `apk_revival/meego/engine/ecology.py` | Replenishes bounded wild node pools at known free sites and applies the one-time additive 75-food bush migration. |
| A | `apk_revival/meego/engine/effects.py` | Handles supported owned temporary boosts, hair/age/Mojo items and child-play effects with expiry/cooldown receipts and rejection of unsupported effects. |
| A | `apk_revival/meego/engine/food.py` | Accounts for elapsed per-minute food consumption with carried fractions, saved deadlines and living-resident counts. |
| A | `apk_revival/meego/engine/harvesting.py` | Composes base stats, matching owned equipment and active item modifiers into final job yield/timing values. |
| M | `apk_revival/meego/engine/local_game.py` | Aligns villager ages to the configured hour scale, synchronizes Mojo/progression and validates original tutorial task acknowledgements. |
| A | `apk_revival/meego/engine/population.py` | Varies only future births/arrivals using original birth-eligible appearances and stones, with explicit local genetics/stat policies. |
| A | `apk_revival/meego/engine/production.py` | Implements original industrial activation/timing and finite stock cycles, validates depots, and validates paid commercial timing/costs; commercial payouts remain missing. |
| A | `apk_revival/meego/engine/progression.py` | Tracks supported earned births, production uses, collections, time and tutorial objectives without fabricated currency rewards. |
| M | `apk_revival/meego/engine/server.py` | Initializes no-bonus villages, migrates local metadata, fixes native building-expiry/final-pickup projections and integrates typed gameplay responses. |
| M | `apk_revival/meego/engine/simulation.py` | Integrates completed-trip harvesting, exact depletion, 75-food bushes, fixed aging deadlines, food, skills/school, arrivals, equipment, effects and production. |
| A | `apk_revival/meego/engine/skills.py` | Credits skill growth from actual delivered work and handles supported stat consumables, school sessions and report cards. |
| A | `apk_revival/meego/frame_pacing.py` | Selects reviewed 60/90-Hz timer patches from verified active Android display modes with conservative fallback. |
| M | `apk_revival/meego/verification.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `apk_revival/portable.py` | Provides the selected APK to the command-line portable Meego backend for catalog/rule loading. |
| M | `apk_revival/rebuild_game.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `apk_revival/restoration.py` | Publishes the new artifact reference only after backend data preparation succeeds, preserving a prior working artifact on failure. |
| M | `apk_revival/runtime.py` | Improves ABI/install errors, resolves actual launcher activities, connects the Android surface, checks process startup and bounds service cleanup/probes. |
| M | `apk_revival/saves.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `apk_revival/store.py` | Validates library profiles independently, reports malformed entries and avoids losing the entire visible library when one entry is broken. |
| M | `apk_revival/ui.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `apk_revival/util.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `apk_revival/verification.py` | Trailing blank line/newline only; logic/content unchanged. |
| M | `resources/APK-REVIVAL-LICENSE.txt` | Trailing blank line/newline only; logic/content unchanged. |
| M | `resources/GPL-3.0.txt` | Trailing blank line/newline only; logic/content unchanged. |
| M | `resources/LGPL-3.0.txt` | Trailing blank line/newline only; logic/content unchanged. |
| M | `resources/LINUX-LIBRARY-NOTICES.txt` | Trailing blank line/newline only; logic/content unchanged. |
| M | `resources/OMNIPC-LICENSE.txt` | Trailing blank line/newline only; logic/content unchanged. |
| M | `resources/PYTHON-LICENSE.txt` | Trailing blank line/newline only; logic/content unchanged. |
| M | `resources/SDL2-COPYRIGHT.txt` | Trailing blank line/newline only; logic/content unchanged. |
| M | `resources/THIRD_PARTY_LICENSES.md` | Trailing blank line/newline only; logic/content unchanged. |
| M | `resources/apk-revival.svg` | Trailing blank line/newline only; logic/content unchanged. |
| A | `resources/managed-waydroid-desktop-session.sh` | Supports an explicitly selected, user-owned KDE Wayland display and cleans up its owned Android session. |
| A | `resources/managed-waydroid-session.sh` | Discovers the single nested display output, sizes it, starts Android and watches display loss for owned-session cleanup. |
| A | `resources/managed-waydroid-startup.sh` | Uses existing shared-storage/controller integration during authorized runtime startup. |
| A | `resources/managed-waydroid.sh` | Starts the existing verified main Waydroid image with a validated opt-in desktop path or the existing Cage fallback. |
| M | `resources/meego-starter.json` | Trailing blank line/newline only; logic/content unchanged. |
| M | `resources/pyinstaller-COPYING.txt` | Trailing blank line/newline only; logic/content unchanged. |
| A | `resources/waydroid-askpass.sh` | Shows the existing runtime authorization prompt through kdialog without storing the password. |
| A | `resources/waydroid-auth-display.sh` | Restores the launcher parent display for runtime authorization dialogs. |


## Solo gameplay follow-up

Branch now includes commit35452faf00b5af163d3219d8c9dec929fcb8a704
(Port solo Meego adventures and earned offline rewards), parentb2e07a3.
22additional files changed; full updated source and95regressions are in
apk_revival/meego/. See its OFFLINE_STATUS.md and four feature-rule documents
for implementation, local balance and limits.450source tests passed,9skipped;
95shipped checks also passed using packagedPython3.12 and in the exactexport.
A separately signed reviewAndroidpackage ata.apktv.meego and Desktop
APK Revival Solo Review shortcut are available locally, using isolated funded
test data. Actual activity launch/request flow succeeded; manual dungeon UI
confirmation remains pending. Main app and personal village unchanged.
