# Version history

Product milestones V1 and V2 correspond to early software versions 0.1.0 and 0.2.0. Releases remain previews until Steam Deck / Android hardware verification is complete.

## [0.9.3] - 2026-10-18

Trees, rocks and bushes now hold 250 materials at completed burg level 1,
plus 50 for every completed burg upgrade. Existing nodes gain only the extra
capacity, preserving resources already harvested. Respawns check every 60 seconds,
with independent limits of five trees, five rocks and five bushes. Old five- and
fifteen-minute schedules retain their cycle start when shortened. No offline
spawn backlog is accumulated; occupied terrain is never overwritten.

Villagers now carry 20 materials at strength 10, plus 2 per ten additional
strength (28 at 50, 38 at 100). Equipment/effects still compose once, fractional
carry persists across trips, and storage/remaining stock bound actual delivery.
Research retains its existing intelligence scaling.

### Verification scope

Ecology, stock migration, burg upgrade, restart, depletion and cap regressions
pass locally. Full unit suite passes except three existing root-account runtime
access errors. Original Android APK and Steam Deck gameplay are not available in
this environment; Android hardware verification remains pending. Existing nodes
above the new cap are preserved and block replacement until harvested below five.

## [0.9.2] - 2026-10-17

### Fixed

**Playing games**
* Pressing Play more than two minutes after APK Revival had started Android (for example after a backup, or after a failed launch) could stop Android with "authorization did not finish within 110 seconds". It now sees that Android is already ready.
* Play time no longer counts time the Steam Deck spent asleep.
* Games played from their original APK now record "last played", so they sort correctly under Recently played.
* If Android could not be reached when a game stopped, its "Log connections" proxy could stay switched on for all of Android. It is now marked and reset on the next Play.
* After a dropped Android connection is recovered, the network proxy and controller taps are set up again instead of silently stopping.
* The 5-second running-game check no longer writes a log file each time (about 700 an hour) or crowds real errors out of diagnostics. Old ones are cleaned up.

**Saves and per-game features**
* Save backups with any part larger than 512 MB could be made but never restored. They now restore, and the limit for a whole backup is 32 GB.
* A failed backup no longer leaves a broken file that shows up as the latest backup.
* Force landscape now picks the right rotation for Android's display instead of possibly turning it to portrait.
* Controller taps follow screen rotation.
* In "Answer for dead servers" mode, the game's own local services on the Deck are still reached. The network log no longer grows without limit, and open connections close when the game stops.
* Edit controls now sits next to Stop game while a game is playing. Before, it could only be reached with the controller's Y button.

**Controller**
* One press of A on a button that opens a question no longer answers the question as well.
* Dropdown lists can now be moved through, chosen and closed with the controller.
* Unplugging one of two controllers no longer makes the other press every button twice.
* Controller focus stays on your game after the library refreshes.
* Game options can no longer be opened with the Y button while a game is running. Restoring or testing from there could stop the game.

**Importing, updating and preparing**
* An import interrupted by a full disk or power loss could leave a game that could be neither imported again nor removed. Imports now finish all at once, and such leftovers are cleaned up on the next import.
* Importing an XAPK for a game already in the library now adds its missing OBB and split files instead of silently ignoring them.
* APKs containing a single file larger than 512 MB can now be imported.
* Games show their real name when the preparation tools are not installed.
* Each update left a full copy of the old app behind, and each Prepare left several copies of the APK. Only the newest previous app is kept now, and leftover files are removed.
* A Steam shortcut for a game that was removed now opens the library with a message instead of failing silently.

### Verification scope

* Each fix has a regression test that fails without it (tests/test_bug_hunt.py), plus offscreen checks of the new Edit controls button, the Game options guard and dropdown control. Behaviour inside Android (rotation choice, controller taps after rotation, proxy reset after a lost connection) has not yet been observed on the Steam Deck.

## [0.9.1] - 2026-10-17

### Changed

* **New logo**: a white pixel-art heart with a play button, on black. It is used for the app window, the application menu and desktop shortcuts (which switch over automatically after updating) and the README. A newly created APK Revival Steam shortcut now uses it as its icon too.

### Verification scope

* Only artwork and the Steam shortcut icon changed; no Android, runtime or game behaviour is affected. The logo was checked at 16 to 1024 pixels. It has not yet been seen in the Steam Deck taskbar or in Gaming Mode.

## [0.9.0] - 2026-10-17

### Added

* **Controller-to-touch mapping** for touch-only games. Start the game, then open Game options > Controller > Edit controls: APK Revival takes a screenshot of the game, and you click where each controller button (A, B, X, Y, bumpers, stick presses, D-pad, Back and Start) should tap. While the game window has focus, pressing a mapped button taps that spot. Mappings are saved per game; leave all buttons empty to turn it off.
* Taps go through one open Android shell, but each still takes about a fifth of a second, so this suits menus, card, puzzle, idle and strategy games better than fast action. If taps cannot start, the game still launches without them.

### Verification scope

* Tests cover stored mappings, screen-size parsing, tap positions, the tap shell and that controller presses are forwarded once per press and only while APK Revival is not the focused window, against a simulated Android guest. Taps have not yet been observed in a game on the Steam Deck's Android, and Steam Input in Gaming Mode may need the controller layout set to Gamepad for presses to reach APK Revival.

## [0.8.0] - 2026-10-17

### Added

* **Library sorting**: recently played (default), name, recently added or ready to play first. The choice is remembered.
* **Play time** for each game, shown in its details.
* **Crash logs**: when a game crashes or fails to start, Android's crash records naming that game are saved automatically (up to 20 per game). View and copy them from Game options > Troubleshooting > Crash logs. They are not added to diagnostics exports.
* **Steam library artwork**: Add game to Steam now also creates a tall cover, wide banner and header image from the game's icon and name, so it looks like a real title in Gaming Mode.
* **Display settings per game**, in Game options: smaller, default or larger text and buttons (Android screen density) and Force landscape. Applied while the game plays and restored afterwards, including after a crash.
* Game options now scrolls, so its buttons stay on screen at 1280 × 800.

### Verification scope

* Tests cover play-time accounting, sorting, crash capture and filtering, Steam grid files and display apply/restore against a simulated Android guest. The display settings, crash capture and Steam artwork have not yet been observed on the Steam Deck or its Android.

## [0.7.0] - 2026-10-17

### Added

* **ARM game support check.** Most Android games are built for ARM phones and need translation on a PC. Setup > ARM game support shows whether your Android has it (and which translator), and the library flags games that need it. When a game cannot start for this reason, a guided setup opens with copyable commands for the community waydroid_script tool, recommending libndk on AMD (such as the Steam Deck) and libhoudini on Intel.
* **Network setting for each game**, in Game options, applied only while the game plays:
  - *Log connections*: the game stays online and APK Revival records every server it contacts (Game options > View network log; also in diagnostics exports).
  - *Answer for dead servers*: no internet; plain web requests get an instant empty reply and secure ones fail at once, so games stop hanging on servers that no longer exist.
  - *Block internet*: a firewall rule for that game alone.
  Secure connections are recorded by server name only, and URL query strings (which often hold tokens) are never logged. Settings are undone when the game stops, and anything left from a crash is removed before the next Play.

### Verification scope

* Tests run the proxy against real local sockets (relaying, tunnelling, offline answers, oversized or invalid requests) and check the Android firewall and proxy commands and the ARM logic against a simulated Android guest. None of this has yet been run on the Steam Deck's Android: Android's proxy and firewall behaviour, and whether a given game respects the system proxy, still need to be observed on hardware.

## [0.6.0] - 2026-10-17

### Changed

* Game-specific support now lives in **game plugins**. The app download and its source zip no longer contain any game-specific code; Meego support is published separately as `APK-Revival-plugin-meego-0.6.0.zip`.
* Setup has a new **Game plugins** card: download the plugins your games need from the matching official release (checksum-verified), or install a plugin file. Plugins are kept in your data folder across app updates. After updating, the app offers to download any plugin your library needs.
* Games whose plugin is missing show **Plugin needed** in the library instead of failing, and keep their files and saves.
* Rewritten README describing the app as it is today, with new screenshots.
* Tidy-up: older handoff logs moved to docs/history/, a duplicate changelog heading renamed, and GitHub Actions updated to current versions.

### Verification scope

* Tests prove the core app runs with no plugin code at all and that the published plugin file restores support, both in Python and inside the packaged Linux app. Meego's own regression tests pass. The plugin download and update prompt have not yet been used on the Steam Deck: after updating, accept the plugin prompt (or use Setup > Game plugins) and check that Meego still opens and plays in Android.

## [0.5.1] - 2026-10-17

### Fixed

* Closing a game now ends its session automatically, without pressing Stop game. Android keeps closed apps cached in the background, so the launcher previously saw a live process and kept waiting. It now also checks whether the game is still on screen, and ends the session after about 15 seconds off screen. A brief pop-up from another app, such as a sign-in dialog, does not end the game, and unrecognised status output never does.
* A game started from its own Steam shortcut now closes APK Revival when the game ends, returning straight to Steam.

### Verification scope

* Automated tests simulate Android 10 to 13 activity status output, a sign-in dialog, failed status queries and similar package names. The on-screen check has not yet been observed on the Steam Deck's Android; if a game still needs Stop game, report it so the detection can be adjusted.

## [0.5.0] - 2026-10-17

### Added

* Open XAPK, APKS and APKM bundles directly, from Add game, drag and drop or the file manager. The base APK, its split APKs and expansion OBB files are imported together; encrypted or mismatched bundles get a clear message. Expansion files of several GB are supported.
* Back up and restore any Android game's progress from Game options. Backups cover the game's private data (without caches) and its external data folder, where engines such as Unity keep saves. Restoring first backs up the current progress, never writes links or files outside the game's folders, and fixes Android file ownership.
* Remove a game from the library. Its saves and backups are kept in a removed-games folder. Optionally uninstall it from Android too: its progress is backed up first, and nothing is uninstalled if that backup fails.
* Add a single game to Steam from Game options, with its own icon, so it starts straight from Gaming Mode.

### Verification scope

* Automated tests cover bundle import, backup and restore commands with a simulated Android guest, removal and Steam shortcut records. Backup, restore and uninstall have not yet been run against a real Android guest on Steam Deck hardware; try them first with a game whose progress you can afford to lose.

## [0.4.0] - 2026-10-17

### Improved

* Official release of the Deck builds 0.3.19 through 0.3.27, which were previously installed only on one Steam Deck: offline Meego gameplay (solo adventures and dungeons, research, fishing, Temple levels, food and hunger, strength-based carrying, resource respawning, building moves, three Launch Dock islands and birthsign cards), the optional Meego Mods menu with the in-game Skip timer, and the Waydroid runtime and fullscreen launch fixes.
* Includes the 0.3.8 Windows-style launcher and the fix that queues a click made while another task runs, so Check for updates is never silently ignored. Update check errors appear on the Updates card.
* Version 0.4.0 is higher than every Deck-only build, so installs on 0.3.19 to 0.3.27 are offered this update in the app. Games, saves and prepared Meego data stay in the separate data folder.
* Added AGENTS.md and CLAUDE.md so every AI assistant reads and updates the shared log in docs/AI_HANDOFF.md.
* Tests no longer depend on Steam Deck only programs or paths (Waydroid, SteamOS Waydroid scripts, /usr/bin/sudo or /usr/bin/visudo), so they run on GitHub's Ubuntu builders.

### Verification scope

* The full automated suite passes on Linux, including the runtime access tests as a non-root user with a real visudo. Gameplay behavior is as recorded per version in docs/AI_HANDOFF.md; items listed there as pending native or Android acceptance remain unverified on hardware.

## [0.3.27] — Repair villager birthsign card lookup

- Send villager birthsign IDs as strings at the native HTTP boundary, matching original card-menu dictionary lookups. Preserve saved numeric genetics and collection membership IDs.
- Cover all 35 original card records, full/partial responses and JSON roundtrip; no native APK patch or trait replacement. Nooni's saved Owl remains Owl.

## [0.3.26] — Repair Launch Dock 0/0 capacity

- Populate login/resume questing_villager_limit from original completed Dock rules (4/8/12/16). The native menu reads this separate configuration table, which old prepared seeds left empty.
- Apply at response time without changing the signed APK, existing private configuration, island or progress. Add cached-seed and all-upgrade-level regressions.

## [0.3.25] — Three offline Launch Dock islands (pilot)

- Add Pebble Bay, Timber Cove and Berry Haven through the original neighbour and visited-island screens. Separate remote snapshots from home state; validate island identities.
- Persist adult departures, timed offline returns, storage-limited resource rewards and one-time charisma gains. Preserve villagers, inventory, home housing and saved deadlines; prevent duplicate claims within a trip.
- Respect original Dock guest capacities; update trip references when moving the Dock. No cloud model, external server, game reset or APK patch. Native UI acceptance remains pending.

## [0.3.24] — Make strength affect resource carrying

- Increase local resource-yield scaling from one per100 extra STR to one per10. STR24 now averages3.4 basic resources per trip, with a five-unit base cap before original equipment/effect bonuses. Research INT behavior is unchanged.
- Preserve fractional trip accounting, finite last-unit collection, storage limits and delivered-unit skill growth. No save edits or APK preparation required.

## [0.3.23] — Correct temple hunger and freeze closed-game food

- Derive native hunger from the actual food bank instead of leaving the starter mood flag permanently hungry.
- Freeze passive food consumption and harvesting while closed/paused; keep bush/farm stock intact and resume normal active food use on return. Preserve other offline progress and existing supplies.
- Add food-session regressions covering clean/unclean restart, paused polls, fractional accounting and concurrent offline wood gathering. No new native APK preparation is required.

## [0.3.22] — In-game Skip timer

- Place Skip timer beside X in Meego's shared baby, child and building countdown panel. Explicit clicks finish selected supported work without skull cost; normal timers remain unchanged.
- Keep the launcher picker optional, refresh new tasks automatically, clear stale selections and bound state-lock waits. Avoid redundant APK integrity hashing on picker refresh while retaining Play checks.
- Validate the exact native library and panel asset; preserve the existing signing identity and village. User confirmed in-game Skip timer worked on the Deck.
- Record the focused audit and ten offline NPC-island feasibility work in docs/MEEGO_SMALL_AUDIT_0322.md. Launch Dock visits/rewards are not implemented yet.

## [0.3.21] — Optional Meego timer mod

- Add Meego's Mods menu in the launcher with an explicit Enable Skip timer switch and a selected-task picker. Nothing is skipped automatically.
- Finish active construction/upgrades, industrial preparation, Skool classes, baby/child growth, item cooldowns, or the next capped resource respawn without charging skulls or advancing the island clock.
- Reject expired/replaced task selections and duplicate completions. Persist each chosen change atomically through the running game's existing local service, with a bounded mod history.
- Preserve the native APK, saves, normal timer policies, reward-collection actions and launcher design. This first menu is in APK Revival, not injected into native Meego panels.

## [0.3.20] — Merged launcher candidate

- Integrate the upstream v0.3.8 launcher redesign with the tested Deck Meego engine and runtime fixes. Keep all game data separate from this candidate build.
- Preserve managed runtime recovery, input diagnostics, existing APK analysis, and no-bonus new-village actions.

## [0.3.19] — Meego camera input and display timing (candidate)

- Repair the native move gate so rejected events do not restart its waiting period. Preserve gesture thresholds, camera bounds and existing controls; require the exact reviewed library and instruction bytes.
- Select the reviewed 90-Hz render timer on Play only when Android reports active 90-Hz modes. Retain the original 60-Hz timer for missing, mixed or unsupported mode reports. Rebuild older Meego clients once through the existing signed restoration workflow, preserving saves and prior working artifacts on preparation failure.
- Keep the previous artifact reference if local-service data preparation fails or is cancelled.

### Verification scope

After the user authorized a trial, the 0.3.19 launcher was built and installed. All 58 targeted source tests, seven packaged camera tests, version/certificate probe and offscreen smoke passed. An isolated signed game build passed signature/alignment and signing-identity checks. The live cold-start attempt timed out at runtime authorization before game installation/launch; camera smoothness and physical latency remain unverified.

## [0.3.18] — Completed building timer contract

- Correct the native no-expiry field for idle/completed Meego buildings. Saves retain their internal timer values; HTTP responses omit a zero building expiry so Meego does not treat a completed hut as overdue and repeatedly request an update. Active construction deadlines and villager timers remain intact.

## [0.3.17] — Nursing deadlines, resource replenishment and tool crafting

- Keep baby/parent job expiry on the child's fixed birthday deadline across 10-second polls and restarts; grow babies into children and children into adults using the existing local age scale. Respect each villager's saved deathday and exclude dead villagers from the displayed food rate.
- Restore missing resource nodes at known unoccupied sites, with the original pools of four rocks, three trees and three bushes. The supplemental 15-minute cadence is a local restoration policy; the original client also recovers missing nodes on startup.
- Support original resource and prior-tool purchase recipes, prerequisite research, native flat research cursors, and item limits including equipped tools. Preserve existing inventory and research.
- Audit bundled catalogs without claiming all server-dependent mechanics work. Catalog/aging/respawn tests and remaining native checks are recorded in the handoff.
- Correct food consumption to the native per-minute units, preserve fractions, and start the new rate without retroactive deductions. Count actual delivered resources toward the local 60-unit STR/INT growth threshold.
- Restore the 35 original birthstone records through a newer metadata patch and preserve earned, tiered discoveries. Existing prepared APKs and saves remain in place; native popup validation remains required.

## [0.3.16] — Local gameplay timing and managed connection recovery

- Credit Meego resources after completed trips; preserve fractional progress and existing bank balances. Replace the earlier uniform 500 node stock with documented local stock sizes.
- Add persistent owned newcomers with housing limits, productive-work stat growth, supported permanent stat items and one-hour Skool classes with native report-card response fields. Original server balance remains unrecovered; these policies are documented in `docs/MEEGO.md`.
- Recover transient ADB disconnections and the owned local-service reverse port with bounded checks. Keep suspended guests paused and preserve live backend/save state during recovery.
- Stop an owned Android session before closing its compositor, release startup log handles, and keep shared sessions untouched.
- Keep healthy library entries usable when another profile is damaged. Report the affected profiles and actual launcher version in diagnostics.
- Serialize Play/Stop with background status checks. Add private local library-control requests for unattended testing through the same normal UI workflow.
- Wait for owned runtime setup authorization before announcing Play success. Bound that wait and cancel the owned compositor process group after orderly session shutdown, including its pending authorization dialog.

Verification scope: source, real Qt and host TCP tests are recorded in `OVERNIGHT_HANDOFF.md`. Live runtime, physical controls, reboot and native gameplay checks are listed separately there; passing simulation tests does not certify complete original-game parity or a touchscreen latency improvement. Android/Waydroid remains the internal runtime dependency. No launcher redesign, Android reset or save wipe is included.

## [0.3.15] — Runtime authorization display and retained logs

- Preserve the actual parent display context before Cage and restore it for graphical authorization, so post-start password dialogs use the desktop rather than Android's private display.
- Keep private startup logs after launcher exit and record their path in runtime diagnostics.

Verification scope: 52 targeted runtime/authorization checks and packaged startup checks passed. A real Deck read-only check verified parent-display routing. Android remains the internal runtime dependency. The exact graphics crash trigger, camera lag and normal-app authorization/cold-start validation remain unresolved in this release.

## [0.3.14] — Meego temple capacity and fresh villages

- Count the bundled villager capacity of all building states, including the starter temple's five slots and existing capacity during upgrades. The former huts-only check incorrectly rejected starter breeding.
- Start new local villages with two Meego and zero bonus resources or crystal skulls; prevent restart from refilling them. Add Game options > New village (no bonuses), with an automatic backup of the previous village.
- Test hut construction, completion polls, movement, saved state and capacity. Record the real island/menu frame comparison and the observed repeated hut update requests.

Verification scope: private bundled-rule tests cover the capacity correction, legitimate starter breeding and no-bonus save persistence. Android remains the runtime dependency. Original server starting values, complete game balance, visual hut synchronization and physical drag/pinch improvement are not yet certified. The new local defaults are an approximation, not a claim of an exact original base-game recreation.

## [0.3.13] — Meego action failure protocol repair

- Send rejected local actions through the native client's HTTP failure callback, with its expected JSON-encoded exception field. A successful HTTP 200 must not carry a rejected pairing result.
- Keep breeding tokens, housing requirements and duplicate-birth protection. Record useful action errors and display them in APK Revival without stopping the running game.
- Preserve the existing APK and village; reimporting the same original APK reuses its library entry.

Verification scope: private-rule simulation/request-parser regression checks cover rejected pairing, valid pairing, retries and saved state. Static ARM analysis of the original Meego client establishes HTTP callback selection and exception decoding. Android remains the runtime dependency. Visual pairing recovery and island/menu rendering comparison remain pending on the real Deck; no latency improvement is claimed.

## [0.3.12] — Connection discovery without DHCP lease data

- Recover the current Waydroid connection when its DHCP lease file is empty by matching the installed container's configured MAC and the guest's actual interface address.
- Reconnect through the configured bridge's matching neighbour when no current ADB transport exists; do not scan networks or select arbitrary phones/emulators.
- Record the runtime status and selected address source privately for launch diagnosis.

Verification scope: identity/discovery regression checks and packaged startup checks are recorded in the investigation report. The real Deck lease file is empty while ADB retains a connected guest; its guest MAC matches the installed LXC identity. Successful normal-app launch, rendering and touch improvement remain unverified. No Android data was reset.

## [0.3.11] — Launch-time display and timeout repair

- Reject an unresponsive session-reported Cage socket and a cached SurfaceFlinger layer list without a live graphics composer; recover the managed image once.
- Name the actual activity-launch steps and bound activity resolution, start, process confirmation and cleanup separately.
- Start without waiting indefinitely for Android's first-draw acknowledgement; keep process confirmation and useful errors.
- Preserve the original launch failure if cleanup also fails, and release local backend connections with short timeouts.

Verification scope: regression checks and packaged smoke results are recorded in the investigation report. Live logs confirm composer disconnection, SurfaceFlinger failure and no focused Meego window. The prior process-scoped REA test can terminate descendants it launched, so it is no longer used to start a long-lived Android runtime. Actual app Play and pinch improvement remain subject to device validation; no saves were reset.

## [0.3.10] — Managed game runtime and repaired gesture capture

- Wake a suspended container through Waydroid’s own DBus launch mechanism; preserve suspend policy.
- Play checks display readiness and performs at most one recovery of the existing managed Android image after confirmed display-service failure.
- Stop the launcher-owned session when its private Cage display disappears, avoiding the observed stale RUNNING state.
- Use shared-storage and controller startup helpers without reapplying the installed bundle's broad permission/sysctl/privileged-app changes.
- Apply game-scoped immersive presentation when no custom display policy exists, restoring the previous setting on Stop.
- Fix Android 13 focus detection and collect native frame intervals plus game input acknowledgement snapshots during gesture trials.

Verification scope: automated runtime/presentation/recorder/supervisor tests and packaged smoke checks are recorded in the investigation report. The user reports mainly touchscreen pinch zoom stutters. Android graphics failure recurred during live observation. No physical latency or pinch improvement is claimed until a healthy-session comparison is obtained; Android remains the internal runtime dependency.

## [0.3.9] — Local input diagnostics build

- Add Setup > Capture input diagnostics for Meego touch/mouse and Android screen comparisons. Record actual reported display names, focus, input configuration and available HWUI frame deltas without changing settings or restarting Android.
- Add Restart Android with existing-profile validation and bounded shutdown; preserve Android data. Discover the actual private compositor output instead of assuming its name.
- Keep rendering measurements separate from physical touch latency; native OpenGL frame coverage can be unavailable.

Verification scope: collector tests and offscreen Android-free UI checks pass. Live REA inspection found a failed Android graphics stack. Physical pinch/touch/mouse comparison and cold-runtime recovery remain unverified. No Android performance or input tuning was applied; the cause of Meego zoom stutter remains unresolved.

## [0.3.8 local build] — Local managed APK opener build

- Play ordinary APKs without requiring a restoration adapter; keep prepared restorations and their backend/saves on their existing path.
- Read APK label, package, icon, launcher activity and ABI metadata. Handle Dolphin file-open requests and drag-and-drop imports.
- Manage the installed SteamOS Waydroid main profile through its mount/service helpers and Cage. Use graphical authorization instead of Konsole.
- Discover current Android IP, wait for boot/package manager, resolve the actual launcher activity, preserve installed data and skip identical APKs.
- Register Dolphin MIME association and support safe Steam shortcut registration while Steam is closed.

Verification scope: Android launch from stopped runtime, second launch, reboot recovery and retained Android data are **blocked by the agent sandbox** on this build. Opener unit tests and offscreen Qt workflow tests pass. This is a local candidate, not a certified gameplay release.

## [0.3.8] - 2026-10-15

### Improved

* Redesigned the launcher in a Windows 11 style: a left navigation pane (Library, Setup, Updates) that collapses to icons on narrow windows, a status bar, and content dialogs with button footers.
* Setup is now grouped into Windows Settings style cards for preparation tools, Android, updates, and desktop and Steam integration. Each card explains what it does in plain language. All previous actions remain available.
* Library tiles show each game's own launcher icon from the imported APK (or a generated tile when none is available), its version, and a clear status: Ready to play, Needs preparing or Not supported yet.
* The details pane lists version, package, engine, required and target Android versions, architecture, size, preparation method, date added and last played.
* Newly imported games use their real name when the APK stores it as a compiled resource, instead of the file name.

### Verification scope

* Automated unit and native Qt tests cover the redesigned interface, controller focus and the Setup layout at Steam Deck and minimum window sizes. The new look has not yet been checked on physical Steam Deck hardware, and Android gameplay verification is unchanged by this release.

## [0.3.7] - 2026-10-13

### Improved

* On Steam Deck installations using the SteamOS Waydroid Bundle, the Play and Start Android actions recognize `~/Android_Waydroid/waydroid.img` and its existing Cage launcher. They start the main-profile launcher when its Android session is stopped, rather than trying the generic uninitialized host session.
* The bundled ADB tool reconnects to the guest's reported IP automatically, and Play waits for that connection before deploying and starting the previously prepared client and local backend. No new preparation or data reset is performed.
* Reuse a running Android guest without launching a second Cage session. If administrator authentication is necessary, use an interactive SteamOS Konsole prompt. Otherwise use a valid cached sudo authorization for streamlined startup.
* Setup now explains bundle-aware Play and routes Start Container through the existing-image launcher when present.
* Added tests for first launch, automatic reconnection, cached vs interactive authentication, and avoiding duplicate sessions.

### Verification scope

* Automated unit and native Qt tests check the Play orchestration and SteamOS Android startup boundaries. Steam Deck device-specific Cage/sudo behavior and Meego gameplay still require live verification; an ADB connection is not proof of offline gameplay.

## [0.3.6] - 2026-10-13

### Fixed

* Isolate external SteamOS graphical processes, especially Konsole, from APK Revival's bundled PySide6 Qt plugin, font, QML and headless platform environment. Prevent Qt launcher aborts when Start Container requests administrator authorization.
* Preserve normal host Wayland/display configuration and system Qt search paths while removing packaged internal plugin locations.
* Add a focused automated regression test for Konsole's environment after a frozen APK Revival launch.

### Verification scope

* Automated unit and native Qt packaging tests cover environment isolation. Physical Steam Deck Android/Waydroid authorization and Meego gameplay remain unverified pending a device test.

## [0.3.5] - 2026-10-13

### Fixed

* Prevent SteamOS `systemctl`, Waydroid, ADB, Konsole and external tools from inheriting APK Revival's bundled OpenSSL and Qt library directory after automatic updates.
* Filter private library paths even when a previous packaged launcher has already written them to `LD_LIBRARY_PATH_ORIG`. Keep ordinary original system library locations available.
* Start update compatibility probes and relaunch processes with an isolated host environment, avoiding nested bundled library paths across future updates.
* Added regression tests for the photographed Steam Deck `OPENSSL_3.4.0 not found` loader failure. Existing games, profiles and saves are not reset by this repair.

### Verification scope

* Automated checks cover inherited loader variables and external host subprocess boundaries. Real Steam Deck Android/Waydroid connection and Meego gameplay still require a device test; passing host process checks does not establish offline gameplay.

## [0.3.4] - 2026-10-13

### Improved

* Streamlined the library around one main action: **Prepare game** before preparing, **Play** after preparing, and **Stop game** while the selected game runs. Preparation completion switches the button automatically and focuses Play for controller use.
* Existing preparation survives app and Steam Deck restarts. Play attempts Android connection, existing-client deployment and local-backend startup as needed. Android containers that require administrator privileges still need the explicit Setup path.
* Repeated preparation reuses a hash-matched prepared artifact or finished independent rebuild, preserving game data and signing configuration.
* Missing or corrupted prepared files return the game to an explicit repair action; changes to the preferred preparation method require preparation of the new method.

### Verification scope

* Service and native Qt tests cover button transitions, saved preparation state, altered paths and artifact-integrity rejection. Steam Deck Waydroid gameplay and unfinished Meego mechanics are not newly certified by this launcher update.

## [0.3.3] - 2026-10-12

### Fixed

* Generate the HTTP health request inside Android and wait for the reply. A real Deck diagnostic received no response through ADB stdin but returned HTTP 200 and the expected nonce through the guest-generated request. This verifies diagnostic transport, not Meego gameplay.
* Add Open Android and explicit ADB authorization instructions for unauthorized guests.
* Query the Waydroid container service independently of user-session status; omitted status fields no longer falsely block session startup.
* Start container opens a visible Konsole/sudo prompt on SteamOS when available, checks actual service state and explains the next step. Failed starts show a dialog.
* Empty device lists state that Android is not connected. Connection errors and guest IP are visible rather than discarded.
* Discover an existing same-user Wayland socket. On X11, Start Android can use an already-installed Weston for an owned nested display, without installing packages. Session startup errors are captured.

### Verification scope

Container/session discovery, terminal authorization routing, failure reporting, socket selection and empty-device UI are tested at process boundaries. Actual Steam Deck service startup and Android gameplay require device testing.

## [0.3.2] - 2026-10-12

### Fixed

* Private Java is added to the process PATH and JAVA_HOME so Android SDK signing scripts can run it without a system Java installation. Cached private runtimes are configured before tool repair.
* A visible Updates button in the main header opens and scrolls directly to the update controls.
* Setup scrolls vertically on Steam Deck instead of compressing and overlapping Android controls.
* Android and update buttons use two columns with consistent spacing. Keyboard/controller focus scrolls the selected control into view.

### Verification scope

Real Qt layout geometry and focus scrolling are checked at 1280 x 800 and 1000 x 650. Android gameplay is unchanged and remains subject to device testing.

## [0.3.1] - 2026-10-12

### Fixed

* Bundle portable certificate authorities and use verified HTTPS for every preparation-tool, Java and update download. Fix certificate verification failures in frozen Steam Deck builds without disabling TLS checks.
* Validate application installs before replacing an existing app and restore the previous app if the directory swap fails.

### Added

* Setup: Check for updates, download/checksum/compatibility validation, automatic installation and restart with the prior app preserved. Games and saves remain separate.
* Session-only read-only GitHub access for private releases, plus Open releases and Install downloaded update for browser-authenticated downloads without manual extraction.

### Verification scope

HTTPS trust, release selection, credential redirect handling, unsafe archive rejection, checksum failures, update compatibility and installation rollback are tested. Full Android gameplay remains unverified on this build until tested on the Deck.

## [0.3.0] - 2026-10-12

### Added

* Exact-hash adapter for the supplied The Meego v1.32 APK, preserving the native game and preparing a separate Android installation.
* Reviewable bounded native/compiled-resource patches and local service routing through checked ADB reverse communication.
* Reviewed self-authored Meego service integrated into Play/Stop, persistent village saves, reversible backups and portable exports.
* Rules extracted from the user-owned APK into private working data; proprietary APKs/assets are excluded from source and release packages.
* Optional explicit village-save import, preserving an existing launcher save.
* Guided real-Android offline test: guest IPv4/IPv6 restrictions, village/menu observations, building action evidence, save/relaunch and local-service failure/recovery.

### Verification scope

Actual Meego import/preparation/signing, HTTP actions, persistence, backups and exports were exercised locally. Android gameplay was not run here: this environment lacks Binder/Wayland and container privileges. Earlier user-reported Deck gameplay belongs to the earlier Meego release, not this newly signed client. Guided Android checks remain unverified until executed on a compatible guest. Unsupported quests/social behavior and original balance remain incomplete.

## [0.2.0] - 2026-10-12

### Added

* Native Linux launcher with a 1280 × 800 library, local artwork and a new APK Revival logo.
* Add Game → Prepare → Play workflows using the existing V1 engine.
* Touch/mouse/keyboard support and SDL2 controller focus navigation.
* Named background stages, useful errors, guided Waydroid discovery and intended-device selection.
* User-local preparation tools, private Java installation, desktop shortcut installation and Steam instructions.
* Save backup/restore, redacted diagnostics, Advanced evidence views and native portable exports.
* Included self-authored Tap Quest desktop demonstration with persistent progress.
* GitHub release builds, version tags, source archives, SHA-256 checksums and downloadable Linux packages.

### Fixed

* GitHub package startup dependencies: EGL and the full Qt XCB dependency set are installed on the build runner and checked with a real X display.

### Verification scope

The local V2 suite exercised real Qt workflows, actual APK signing, private tool installation and desktop export gameplay/persistence. Android commands are tested at the adapter boundary with doubles. Physical Steam Deck, original Android gameplay, guest networking and physical controller operation remain unverified. No commercial game restoration is claimed. The package targets Linux x86_64, glibc 2.39+.

## [0.1.0] - 2026-10-12

### Added

* V1 Python restoration engine, CLI and legacy Tk workbench.
* Preserved/hash-bound imports, static evidence reports and versioned profiles.
* Explicit signed APK patch operations, local backend and separate rebuild workflows for the self-authored Tap Quest fixture.
* Waydroid runtime adapter, save backups, portable exports and strict offline-verification gates.

### Verification scope

35 local V1 tests passed with actual APK tools and the Tk display enabled. The Android emulator attempt timed out before gameplay checks. This historical release is source-only and does not include the V2 native launcher. Its source remains at the original V1 commit; the historical release tag backfill was blocked by GitHub permissions.

[0.2.0]: https://github.com/onlykappa/Apk-revival/releases/tag/v0.2.0
[0.1.0]: https://github.com/onlykappa/Apk-revival/tree/7458887bf687eaaf8cf29242ba40be518e761abf

[0.3.0]: https://github.com/onlykappa/Apk-revival/releases/tag/v0.3.0

