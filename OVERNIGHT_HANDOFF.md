## 0.3.23 food freeze and temple hunger — installed

User requested food freeze on exit and asked why Temple remains hungry with
food. Read-only live snapshot showed390 food and global_state.mood_state0.
Original native JFVillageService hunger helpers0x8f6b60/0x8f6bf0 test mood<2;
JFTempleHead chooses neutral2, unhappy1 and mad0. Food accounting never synced
that starter flag. New food policy publishes2 for stocked food and1 when empty,
without granting food or a permanent productivity bonus.

local-resident-food-active-session-v2 preserves v1 balance and active fractional
minutes. State startup, first native request, login/resume and paused/logout
polls freeze food; food trips also pause without depleting bush/farm stock.
Aging, wood/stone gathering, resource ecology and production preparation retain
other offline progress. World last_simulated_at is not fast-forwarded to hide
closed time. Active food consumption and harvesting resume normally. Details:
docs/MEEGO_FOOD_POLICY.md. User policy is local, not claimed original balance.

17 focused food tests PASS. Final frozen build380 tests PASS in26.965s, build1
PASS, version/certificate probe0.3.23/true. Temporary-save restart tests cover
clean logout, background polls, unclean host restart, first request without
login, food source conservation, simultaneous wood gathering and retained child
aging. Preliminary runs exposed old tests assuming unchanged session metadata /
unstarted sessions or stale mood after funding; fixed clocks and explicit login
now test those invariants. Final native controls and existing game regressions
pass. No new APK build:0.3.22 native Skip/camera controls remain current.

Installed SHA256a8ff2fb61d71cf0f3e154ccb58e220fedf1d1a3f7e94e1e722bb9a50f046f230.
Receipt build/installed-food-session-update.json. All17 protected files unchanged
across install; no live island edits/reset/refill. Previous app retained under
~/.local/share/apk-revival-app-backups/merged-food-session-20261016-061407/.
User was asked to reopen normally for visual confirmation. Closed checkpoint
/tmp/apkr-food-reopen-checkpoint.json recorded479 food, old mood0; actual Temple
appearance is now user-confirmed: hunger message stopped after normal Play.
Live backend reports positive food, mood2 and v2 policy. Food freeze across
closed intervals passed automated session/restart tests; a manually timed closed
interval was not observed in this session.

## 0.3.22 native Skip timer / focused audit — installed and user-confirmed

Supersedes the earlier launcher-only Mods interaction. Details and known gaps:
docs/MODS.md and docs/MEEGO_SMALL_AUDIT_0322.md. Native shared baby/child/building
countdown panel now has Skip timer beside X, using the original bound completion
button, no skull charge and scoped exact-library patches. Backend native adapter
is enabled only for prepared timer-mod revision1; ordinary clients retain paid
completion. No global time skip. Native partial/stale/duplicate callbacks reject.

363 final packaged regressions PASS (27.165s), isolated signed native APK build
PASS (7.686s), same original local signing identity and exact planned five-member
APK diff. Initial signed build rejected variable-length panel binary operation;
repaired using dedicated exact-file/hash/revision asset operation, preserving
existing binary restrictions. Auto-refresh new picker tasks; clear old selection;
stop timer on close; no repeated UI-thread APK hashes;50ms bounded snapshot wait.

Installed0.3.22 SHA256a27e5eb3e24d3e614214256db2fe7cd2f6551aa8858c0596803496916672d3b3.
Receipt build/installed-native-timer-update.json. All17 protected files unchanged
across install; user closed apps first. Previous app retained under
~/.local/share/apk-revival-app-backups/merged-native-timer-20261016-055820/.
User reopened through normal Play and confirmed "skip timer worked!!". Only the
exercised native path is physically confirmed; no all-menu/reboot/latency claim.

Ten offline NPC islands are feasible but not implemented. Neighbour list currently
empty, send_villager/get_remote_village unsupported; existing get_village ignores
village_id. Recover/isolate native remote packet shapes before enabling visits.
Need persistent traveller return, one-time rewards and explicit local balancing.
Do not claim former-server feature parity or ten working AI islands. Current
focus/audit notes distinguish observed healthy backend from unresolved transient
visual freeze report. Preserve current live island; do not rerun fresh scripts.

# APK Revival / Meego overnight handoff

## 0.3.21 optional Mods / Skip timer (2026-10-15)

### Installation completed after user closed game

Installed0.3.21 after the normal launcher --quit request6b62cbef65654b45a49f93775a190c3d returned succeeded. The earlier lock blocker below is resolved. All17 protected game/configuration files, including current village and APKs, were byte-identical across the atomic application swap. Receipt: build/installed-mods-update.json. Retained previous app: /home/deck/.local/share/apk-revival-app-backups/merged-mods-20261015-213016/APK-Revival-app. Installed SHA256:7f3eba66b15895bc207ddea3858b6f28f61d0d32c5c9af0d429c13bdd4b4326e. Version/certificate probe0.3.21/true. No live timer skipped; physical in-game verification remains pending.

User asked about farms: original TechTree max_count_by_state_meter_unit allows Grub Grub Farm at Temple5, Sawmill at Temple6, Quarry at Temple7. Existing save currently Temple3, no production buildings placed. All three production pathways already implemented. Baseline preparation/output: Farm900s/6500food, Sawmill1080s/19500wood, Quarry1350s/17000stone; original finite stock quantities, local stocked initialization policy as documented in production.py. They require construction, activation/preparation worker and normal harvesting, not passive bank deposits. Respawns serve early gathering, production provides later repeatable supplies. No unlocks/resources/save edits were granted.

Implemented launcher Meego -> Mods -> Enable Skip timer -> choose task -> Skip
timer. The switch defaults off for each menu opening. This first version is a
launcher dialog, not a button injected into native Meego menus. Existing design,
Play, runtime policy and APK remain unchanged. Details: docs/MODS.md.

Supported: assigned construction/upgrades, industrial preparation, Skool class,
baby-to-child/child-to-adult (one stage), recorded item cooldown, next normal
resource respawn. Construction and classes release the corresponding workers;
classes leave report cards for normal collection. Production creates original
finite stock rather than free bank balances. Growth releases nursing, keeps
other people and absolute death dates unchanged. Cooldown skips do not activate
or extend buffs. Ecology reuses safe sites and retains six-per-kind caps.
Research is earned-point work, not a countdown; dungeon jobs, commercial service
expiry, arrivals, death and rewards are not accelerated. No global fast-forward.

The running backend exposes in-process mod_timers/skip_timer methods only, gated
by selected running Meego in Launcher. No HTTP cheat endpoint or out-of-process
save editing. Read-only picker does not save. Under the existing State lock,
skip first settles ordinary elapsed time, validates task-generation token, copies
the state, finishes the selected supported transition and atomically persists
with existing backups. Bounded local_mod_history keeps the last100 skips. Stale
or replayed choices reject; task tokens include worker start/cycle identity and
resource-generation count. Ordinary Play never invokes skip logic.

Verification: final frozen0.3.21 package ran343 tests, all PASS in25.622s;
build/mods-packaged-tests-final.log. Includes15 new backend/UI checks, real Qt
opt-in/worker/status controls, original TechTree rules, selected-only completion,
class reports, original output stocks, parenting, cooldown/buff ownership,
respawn caps, durable temporary-save restart and replay rejection. Build1 PASS;
version/certificate probe0.3.21/true. No live island timer was skipped. Native
on-screen refresh/user gameplay verification remains pending.

Candidate: dist/APK-Revival-0.3.21-mods-final/APK-Revival
SHA256:7f3eba66b15895bc207ddea3858b6f28f61d0d32c5c9af0d429c13bdd4b4326e.
Installation attempt stopped at nonblocking launcher.lock (app open), before
copying/replacing app or reading/writing game saves. User was asked to close when
convenient. Once closed, /tmp/install-apkr-merged-mods.py guards installed previous
SHA9d811f7ff4ce7e609fa25aec5c20be604d96eae5df5db339da343fcb9fc978c5,
retains entire old app and verifies protected files unchanged. Do not overwrite a
running application or manually edit the live island. No public release created.

Work began 2026-10-13 21:22 PDT and resumed after an execution-limit interruption on 2026-10-14. Source tests, observed Deck behavior and remaining release gates are distinguished below. The existing launcher appearance, Android image, original APK and current village were preserved. No public release was published.

## Delivered changes

The local 0.3.16 candidate is installed at `/home/deck/.local/share/apk-revival-app/APK-Revival` and `/home/deck/Downloads/APK-Revival/APK-Revival`. Both executables have SHA-256 `c96e1a728e9bf47466d4d064f32b11a41fe61d789c762f5b40586fa75ef27a68`. The previous executable is retained as `APK-Revival.before-0316`; older backups remain. Updating the app does not restore or replace village data.

Meego now credits gathering after completed trips instead of every second. New rock/tree/bush nodes hold 40/30/20 supplies; baseline trips take 12 seconds. Integer fractional accounting preserves earned units over polling and JSON restart. Stat-growth changes apply between trips, fixing a second polling-frequency dependence. Depleted nodes release all their workers. Existing bank balances are kept.

Owned newcomers use a persisted six-hour timer, housing checks and the original 25-person client ceiling. Migration adds nobody immediately; long offline intervals add at most one. Productive harvesting grows STR and Thinking Rock work grows INT. Supported permanent stat consumables use original item properties without double-counting equipment. One-hour Skool classes persist, award local +1 INT, return the native report-card wrapper exactly once, and cancel without rewards when their teacher is removed/reassigned. **Rates/rewards are documented local restoration policies, not recovered original-server balance.** See `docs/MEEGO.md`.

APK Revival keeps its owned backend during bounded ADB reconnection, validates the current guest and exact service health nonce, and rebinds only its owned reverse port. Paused guests stay paused. Damaged profiles leave healthy library entries usable and appear in diagnostics, which now reports the actual version. Play/Stop button work waits for status checks rather than racing the service lock.

Private `--play GAME_ID`, `--stop-game`, `--restart-runtime` and `--quit` requests run through the normal Qt window/worker. Queued requests are not treated as completed actions. This enables unattended app tests without a short-lived REA capture owning the persistent runtime.

Managed cleanup stops Android's session before releasing the owned Cage group. Startup has a private completion marker: Play waits for post-start authorization instead of announcing success behind a password dialog. Waiting is bounded, and cleanup targets only the launcher-created process group, including pending authorization dialogs. Waydroid remains the runtime behind Play; no Android replacement/removal is claimed.

## Confirmed bugs and root causes

| Bug | Root cause | Repair / evidence |
| --- | --- | --- |
| Excessive gathering / uniform 500 stocks | Native amount-per-trip treated as amount-per-second; old local stocks 500 | Completed trips and documented stocks; finite-stock/storage tests |
| Earned units lost over polling/restart | Binary fractions could truncate 0.999999… | Integer micro-units and JSON-restart conservation tests |
| Different yields around stat gains | An offline batch used the old rate throughout | Apply gains before the next trip; single/split-poll tests |
| Rewards after teacher reassignment | Class completion did not validate its teacher | Cancel interrupted classes; preserve reassigned jobs |
| One bad profile broke library inventory | Profile error aborted refresh | Isolate invalid entries; preserve files and report errors |
| Stop/Play intermittently rejected | Background monitor held serialized job lock | Queue button actions until monitor completion |
| Brief disconnection lost service | Monitor cleaned up immediately | Bounded verified reconnect before cleanup; live trial passed |
| Orphan Cage / password windows | Old cleanup omitted bundle; Cage-only termination left helpers | Graceful session stop then owned group cleanup |
| Play succeeded with password pending | Boot/ADB readiness preceded post-start setup completion | Setup marker gate; updated cold launch succeeded |

## Tests actually executed

Final whole source suite on the actual Deck host: **254 tests, 252 passed, 2 skipped, no failures/errors, 103.560 seconds**. REA evidence `ev_feb37209618d6f030b0630267081fb62e8441a189ff90ffef7c0372eb557e2e4`; report `evidence/overnight-audit/full-suite.json`. The two skips are opt-in legacy Tk V1 windows. Current Qt flows and actual fixture/Meego signing, save/export, backend TCP and protocol checks ran. Android boundaries in some tests use explicit doubles; these passes do not certify Android gameplay.

The missing QtTest testing dependency was supplied from the official PyPI PySide6 Essentials 6.8.3 wheel in user-owned testing directories. SHA-256 `fd57fa0c886ef99b3844173322c0023ec77cc946a0c9a0cdfbc2ac5c511053c1` matched PyPI metadata. No downloaded script was executed. A separate actual Meego Qt import/prepare/guided-cancel test passed in 31.923 seconds. Its first capture ended at the tool's idle deadline just before completion; it was not counted as a pass. The corrected run used an explicit longer deadline.

Source compileall, shell syntax, release version/changelog consistency and whitespace checks passed. Final packaged 0.3.16 certificate/version probe and offscreen startup smoke passed. Offline repacking compiled every project module under CPython 3.12, retaining the licensed installed bootloader/dependencies. No clean PyInstaller build is claimed.

| Real Deck check | Observed result |
| --- | --- |
| Earlier cold Play | Activity/guest rendering succeeded in 17 seconds, but setup password remained pending: this exposed the readiness bug and was not full setup certification |
| Stop / second Play | Succeeded; second Play completed in 3.529 seconds on the existing runtime |
| Updated cold Play | Succeeded with setup completion, 2026-10-14 05:52:30–05:53:20 PDT. The 50-second job includes boot/setup/user authorization; newly discovered display was wayland-1 |
| ADB interruption | Only the verified guest transport disconnected. Normal monitor restored transport and owned reverse in 4.630 seconds, preserving the same game PID and backend nonce |
| Save retention | Current village loaded across Stop/Play/cold start. Original/prepared APK hashes stayed intact; normal food consumption and user gameplay continue changing the save |
| Six-hour newcomer | Actual overnight village changed from 2 to 3 saved people with arrival_count=1; native client continued polling updated village. Local timing/persistence verified; original arrival odds unknown |
| Overnight observation | Normal app stayed alive until user closed it at 05:28; systemd reported 170.8 MiB memory peak. Not a controlled memory-leak test |
| 05:28 shutdown | User explicitly confirmed closing both windows. Composer/SF aborts occurred during shutdown; do not count this as an unexpected gameplay crash. Earlier crash trigger remains unresolved |
| Isolated native mechanics | Separate signed package ata.apkrt.meego / port 8771/private village. Build/install identity verified; first launch reported no process within its bound and later showed splash. Retry hit readiness timeout around pause transitions. Native school/consumable/hut visual checks did not pass |
| Basic Android comparison | Incomplete. Official launch and ADB probes timed out around pause transitions; bounded probe confirmed FROZEN and no new coredumps. Wake-only probes did not establish reliable command readiness. No basic-screen or latency improvement claimed |
| Physical controls / reboot | User-directed touchscreen camera and villager dragging reproduced lag on 0.3.16 at 06:42 PDT; both movements felt delayed/jumpy. Capture completed without focus loss or diagnostic errors. Pinch, edges, fullscreen, controller gameplay and reboot recovery remain unverified |

The first reconnect probe guessed port 8770 and stopped before disconnect; the successful changed trial derived actual production port 18765 from its profile. Persistent launches used the normal user manager, not scenario-owned descendants. Failure records are kept alongside passes.

## Health and performance findings

`evidence/overnight-audit/health-audit.md` and `.json` describe the successful22:15 PDT snapshot: SteamOS 3.8.28 / KWin Wayland, no failed system units, approximately 6.61 GiB available RAM / 309 GiB home storage / 1.21 GiB Android-image storage. Two unrelated Kodi user failures were untouched. Private Java/SDK/signing tools exist and execute; bare-PATH omissions were not missing dependencies. Touchscreen, Steam Deck controller and virtual Xbox pad were detected. Raw touch-node permission denial did not justify chmod changes.

Retained user trials report similar lag with touchscreen and mouse. Guest presentation intervals and outer EGL/dequeue waits indicate uneven native rendering/display pacing; none measures physical touch-to-photon latency. Passive native-Wayland data differs from active X11 trials, and the user still reported lag, so that experiment was reverted. Fresh inspection found only 90 Hz advertised for the actual panel. No unsupported refresh, overclock, security or arbitrary performance tweak was persisted.

`evidence/camera-display-comparison/native-camera-review.md` records native free-pan deltas, selected-item touch gating and actor-follow smoothing. They do not establish a global input delay or a safe native patch. No native controls were altered. **User-reported camera/pinch/character lag remains unresolved; no measured improvement is certified.**

The native 50-ms check uses the initial touch timestamp; it is an initial drag eligibility threshold, not a 20-Hz input cadence. Movement/update handlers do not reset that timestamp. End/cancel/multi-touch transitions remain unverified.

At 06:42–06:45 PDT the user completed a short touchscreen camera/villager trial, then confirmed the fast radial menu was visible for a passive comparison. `evidence/overnight-audit/physical-drag-menu-0316.json` records both successful read-only captures and the user's report that both movements remained delayed/jumpy. The island's recent guest presentation buffer had median/p95/max intervals 16.669/33.315/49.228 ms; the menu-overlay buffer had 16.635/27.322/29.166 ms. These buffers cover only approximately 2.4 and 2.1 seconds respectively, not the whole trials. The menu still shows the island behind it, and the camera/content differ. This supports further native-rendering/display-pacing investigation but is not a controlled workload comparison or a measured improvement. Ten island dispatcher snapshots had at most 6 pending motion events and 32 ms acknowledgement wait, clearing to zero in six snapshots; focus stayed on Meego. Both crash-log captures were empty. No touch-to-photon latency, dropped-tap count or isolated root cause was measured. No APK, controls, runtime configuration or saves were replaced. Broad audits/builds were not repeated during this user test.

Morning host integration check confirmed an executable desktop shortcut, Gaming Mode wrapper and Dolphin APK MIME default `apk-revival.desktop`. Automatic Steam library registration was deferred because Steam was running; its shortcut file was not modified. The wrapper is installed, but Gaming Mode registration and gameplay are not claimed tested.

## Save protection / private testing

Before deployment, current village/profile were copied to `~/.local/share/apk-revival/games/030613cbc63bd03786545999/backups/overnight-20261013-220315/` with manifest. Village SHA-256 `32b5e2b91066246498d093c72b948f3d9438b6e88dac7fe6f98aa8f0254ab7b6`. Updating kept banked supplies; it only capped remaining old resource nodes once. Older ZIP backups remain. Do not automatically restore the pre-test snapshot: later arrivals and user actions are real progress.

Original APK SHA-256 `030613cbc63bd03786545999c3590456a264796866127898928a4d59988d29a2`; production prepared APK SHA-256 `5b00554daae68fd65406b80777878fa03607ac4861da781a07051b29348ebaee`. Neither was replaced.

Private isolated data: `/home/deck/.local/share/apk-revival-testing/overnight-meego/`; separate APK SHA-256 `9fbcfa27321d901416579348361ca803555367f5e3ba95af3348488f11762dc0`. Its optional synthetic supplies/child/Skool and shortened class deadline are test fixtures, not vanilla balance. Never copy them to production or publish proprietary APK/assets. Signature/alignment/separate identifiers and 734 unchanged original entries were verified. The isolated app was closed through normal cleanup, preserving the shared runtime.

## Git commits

Scoped commits since 0.3.15 include `acf7db1`, `030a306`, `2f6923f`, `c410c08`, `cf8bd05`, `ddca00b`, `d6cd59b`, `4abfdde`, `1afafdd`, `f105b1c`, `cfe2725`, `ea27abd`, `b316e2a`, `59a6f4f`, `a78656d`, `2454b5d`, `e6e8458`. Later report/artifact commits are listed by Git. No public push/publish occurred. Interrupted agent turns/capture calls were resumed/replaced; they were not credited as tests.

## Packaging and continuation

The installable archive is a **local candidate**, with unverified native/physical/reboot checks blocking full release certification. Artifact location: `/home/deck/Downloads/APK-Revival-0.3.16-local-candidate.tar.gz`, companion SHA-256 file and source ZIP. Final receipt: `evidence/overnight-audit/packaging.json`. Application/source archives exclude proprietary Meego APK/assets, personal saves, signing keys and raw private logs.

Next priorities:

1. Reproduce paused-runtime resume in a controlled session; preserve suspend policy and distinguish wake/window focus/activity exposure from genuine service failure.
2. Complete isolated native school/report-card/stat-item/newcomer visuals and hut movement/indicator regressions with a stable focused guest.
3. Complete matched island/menu/basic-screen and physical input trials; isolate scene cost, presentation waits and host delivery without speculative native threshold patches.
4. Validate reboot/GamingMode/Steam registration and physical controls. Existing launch wrappers/associations remain; no boot/system change was performed.
5. Resolve cross-worker offline finite-stock allocation and long-offline aging/death-before-school ordering. Original quest/social/treasure/travel/economic parity remains incomplete.

Keep persistent runtime launches under normal app/user-service ownership. Use private request results and job logs to distinguish queued/running/succeeded/failed. Do not reset Android, delete saves or silently replace the current village when continuing.

## 2026-10-14 follow-up: 0.3.17 work in progress

Fixed the reported 10-second nursing countdown reset at the backend contract:
native `JMJob.expire_date` derives last_update + update_interval, so jobs now
count toward fixed birthday deadlines. Parenting is released at the baby's
growth transition; childhood becomes adulthood after offline time; saved
individual deathdays are respected. Starter factory dates now match the
existing one-hour age scale. Exact original server aging/lifespan balance
remains unrecovered. See `evidence/meego-aging.md`.

Integrated the original item-shop recipes/research and supplemental resource
replenishment helpers. Catalog assets/tables were intact; the old handler
rejected resource-priced tools and wrote incompatible research cursor pairs.
Original startup resource pools are four rocks/three trees/three bushes. The
supplemental 15-minute timer is an explicit local policy, using known vacant
resource sites and avoiding offline bursts. Existing village/buildings/stock
and inventory are preserved. 49/50 original shop entries have a validated
recipe or price; Turtle Topper has neither and remains unsupported. Tool
production effects, temporary boosts, appearance potions and server-driven
quest/travel/event acquisition still need work.

Actual host targeted run: **73 tests passed, no failures/errors/skips, 14.904
seconds**, including the privately owned signed APK/protocol/save-export test.
REA `ev_2dd766f1e5e5f3fef01f1b2d8d0d2a36a1d1ba008d45238a7fcd2dd92d2d7b68`;
`evidence/meego-0317-tests.json`. An earlier regression exposed missing initial
ecology metadata, fixed at State startup. A new tool integration fixture first
hit the correct original level-two temple lock; the fixture was corrected to
use the actual upgraded temple state. Neither failed run was counted as a
pass. Source compile and whitespace checks passed.

0.3.17 source-module repack at `dist/APK-Revival-0.3.17` passed its packaged
version/certificate probe and offscreen smoke. The initial harness wrongly
used unsupported --version; the existing --update-probe was used successfully.
`evidence/meego-0317-build.json` records that failure and correction. This is
an offline repack, not a clean PyInstaller build or native gameplay result.
**Installed live app still 0.3.16 at this checkpoint.** Additional user requests
for per-minute food, blank Rabbit birthstones and work-stat gains are now in
progress; rebuild/retest the combined changes before deploying.

Cloud transfer was explicitly canceled by the user. No cloud job, remote
commit, public upload or new environment was created. Current GitHub main was
read-only checked at 0.3.7 and is stale relative to this local checkout; don't
restart development from that remote version.

## 2026-10-14 18:00 PDT follow-up: combined 0.3.17 installed

The work-in-progress checkpoint above is superseded for installation and the
food/birthstone/work-stat tasks. The combined 0.3.17 binary is installed in
`~/.local/share/apk-revival-app/` and `~/Downloads/APK-Revival/`; binary SHA-256
`3594dd8f7388e40d8d8df7bba7d5816fe0e3342051f429caf79080e894620dc2`.
The production village/profile were backed up to
`backups/before-0317-20261014-174429/` before deployment. Neither original nor
prepared APK changed. No Android reset or save replacement occurred.

Food consumption had a confirmed 60-fold unit mismatch: the native client
labels the rate per minute, while the backend charged per hour. Consumption
now conserves integer micro-units across polling/restarts, has no empty-store
debt, and migrates without retroactive increased charges. One food per living
owned resident at home per minute is explicit local balance, not a recovered
original server coefficient. Work-stat gains now count actual credited
resources (60 units per point), including clipped deliveries, rather than one
credit per multi-unit trip. Earned stats and incomplete progress are preserved.

All 35 original birthstone records and their APK images were verified; Rabbit
has original metadata. Login/resume supplies a strictly newer partial original
birthstone table (2.9401) and restores discoveries from owned villagers without
granting unearned stones. Native Rabbit popup contents remain visually
unverified; no claim that an empty server patch erased the bundled table.
Original zodiac distribution, server balance and full gameplay parity remain
unrecovered. See the food, birthstone and work-stat evidence documents.

Actual final combined targeted run: **101 passed, no failures/errors/skips,
13.885 seconds**, including actual APK signing/protocol/save-export. REA
`ev_27d04a630f3186a5669e0f14b9bf13630d8d14b1cc6fcaf46d7ad1877b8e6059`;
`evidence/meego-0317-tests.json`. Combined repack certificate/version probe and
offscreen smoke passed (`evidence/meego-0317-build.json`), REA
`ev_b7b4eed33518dadeb8e97ac5bd98959f5582fd8bcd68ce8e24f211cb19570c9a`.
Compilation and whitespace checks passed again without repeating the broad
0.3.16 suite. This remains an offline source-module repack, not a clean build.

**Real production cold Play after the Deck reboot succeeded** through normal
launcher ownership and graphical runtime authorization. Native API polling
continued. The four pre-update villager IDs, birthdays and deathdays survived.
The overdue baby matured after the elapsed offline time and its parent's
nursing job cleared in the actual save/protocol; animation was not observed.
A normal overdue fifth newcomer arrived without an offline population burst.
Food decreased (492 → 475 → 444 in successive snapshots), with the live rate
5/minute. Birthstone collection tier 1 now contains earned ID 1. Evidence:
`evidence/meego-0317-live.json`; visual tool/respawn/Rabbit checks still pending.

At 17:54 PDT the user completed the 0.3.17 touchscreen camera/character trial.
Focus remained Meego and the capture had no errors. Recent guest presentation
intervals: median **21.212 ms**, p95 **34.775 ms**, max **50.929 ms**, 99 unique
presentations in a retained 2.327-second ring (not whole-trial FPS). Dispatcher
snapshots had 2–9 pending motion events, maximum acknowledgement wait 48 ms.
This is not physical touch-to-photon latency. The user's accepted target is
under **15 ms**, and it is **not reached or certified**. No input control
thresholds were patched.

The actual host panel reports 89.87 Hz; the Android display and SurfaceFlinger
report 60 Hz / 16,666,666 ns. AMD radeonsi hardware rendering is active (Mesa
26.0.8 in Android), so software rendering is not indicated by this snapshot.
The X11 nested output advertises no refresh rate. A clock mismatch is observed;
it does not prove the sole cause of scene stutter. Private device bugreport
SHA-256 `4aa5143b360a0e9453009b2f94ed14cd75adc34ea8a0954dca9a1b1522f89e20`,
REA `ev_7e2eab1759653ee57f105b6b2ff0125ecab6e716cd695232118a9bb81ad5837d`.
Sanitized trial receipt: `evidence/camera-display-comparison/physical-drag-0317.json`.

The generic REA process-capture lifecycle currently fails before target
execution, reporting unverified root-owned Android processes whose environment
cannot be inspected. Repeated calls were stopped; no permission bypass or
root-process cleanup attempted. Dedicated REA ADB tools and the normal app's
validated private request queue work. ADB screen capture also returned
`unreadable_output`; it did not produce a usable visual check.

A bounded native-Wayland display experiment is in progress through the normal
app's Stop → Restart runtime path. Only the installed managed helper's backend
line is temporarily changed from X11 to Wayland, with its exact original
backed up under ignored `private-analysis/meego/pacing-20261014/`. Source and
release helper remain X11 until a matched test supports persistence. The
restart reached the existing SteamOS authorization prompt; the user was asked
to authorize locally. Record its result and restore the original helper if
readiness fails or measurements do not support keeping the candidate.

### Native-Wayland experiment / local packaging checkpoint

Normal Stop succeeded (`595cb0ab2b944c33bb7af7ff3c3f61f6`), runtime restart
succeeded (`13e6d2b898f54b9e8a6534f5e5ac86be`), then Play succeeded
(`672fa771b0ce4193a81cb2528ef9ee21`). Runtime status is ready with the existing
main image, current transport and newly started private compositor. Source
and packaged helper still use X11; only the active installed helper is
experimental Wayland. Do not label this a performance fix. A new matched
touchscreen drag capture has been requested through the existing Setup button;
the last completed report at this checkpoint is still the 17:54 X11 baseline.
Keep or revert the experiment after reading the next report and user feedback.

Combined gameplay changes are saved as commit **6e47b42**. Installable local
candidate and source snapshot are prepared, with metadata refreshed to 0.3.17
instead of the repack donor's stale 0.3.16 documentation. The experimental
helper is excluded. Archive membership and binary hash were verified; old
executable backups, proprietary Meego APK/assets, personal saves and signing
keys are excluded. Current launcher appearance is unchanged.

- `~/Downloads/APK-Revival-0.3.17-local-candidate.tar.gz`
  SHA-256 `e28af4f26308469a9a936827841afd166918d3a5a7610b1af0f685063e5fd171`
- `~/Downloads/APK-Revival-0.3.17-source.zip` (source commit 6e47b42)
  SHA-256 `b785264560f1f04b96598a883689bfa9cc6779d6800b7d7018e4677981477c5f`

Matching `.sha256` sidecars exist. Receipt: `evidence/meego-0317-packaging.json`.
No public publication or push occurred. The old 0.3.16 artifacts remain intact.

Immediate next work: read the requested Wayland capture (actual compositor
output and SurfaceFlinger refresh header, active drag distribution, focus and
dispatch waits), compare to the 17:54 X11 baseline, and preserve the default
only with supported measured/subjective results. Neither a nominal refresh
change nor a successful launch certifies physical latency. Follow with the
pending native Rabbit/catalog/resource/skill visual checks; retain all live
progress and avoid another broad audit or test suite without a new reason.

## 2026-10-14 18:27 PDT: 0.3.18 hut repair verified

Found the cause of the completed Hut's repeated requests: numeric
`expire_date: 0` overrides JMBuilding's native no-expiry sentinel. The JSON HTTP
projection now omits this key for zero-deadline building records; internal
saves, positive construction deadlines, jobs and resource balances remain
unchanged. The baseline was 365 requests in 392.68 seconds, median interval
1.081927 seconds. After the installed update, zero hut requests occurred in a
114-second window while 59 other native requests continued. The user confirmed
**“Hut stopped blinking.”** Static contract and live evidence are in
`evidence/meego-hut-expiry.md` / `evidence/meego-0318-hut-live.json`.

Three HTTP-serialization tests and 17 Meego simulation/protocol tests passed
(20 total, no failures/errors/skips). Packaged version/certificate and
offscreen smoke passed. Installed binary SHA-256
`34492b49e8b244eda054cf8aa32b50f227f04865f5f81ee745dc90dd3e0ab1b8`.
Before-update village/profile backup: `backups/before-0318-20261014-182444/`;
village SHA-256 `38b9fbd9685e81be50608dcafb70742745bff044c3cf2448e7d38c6f0db76788`.
The old native-Wayland installed helper was preserved for the comparison,
and the original/prepared APKs were untouched. Normal quit/install/Play
succeeded through the normal user service and graphical authorization.

Host process capture works again after the runtime lifecycle change; no
permission override was used. Recovered current Desktop KDE Wayland environment
from the user manager. Dedicated passive screenshots now work through normal
ADB byte capture with a 57-byte amdgpu.ids diagnostic prefix removed before the
PNG signature; this is transport decoding, not image editing. Raw screenshots
and traces remain private and excluded from release artifacts.

The user clarifies that remaining trouble is **camera movement and fast pinch
zoom**, rather than moving villagers. The 18:22 native-Wayland gesture report
had median/p95/max guest presentation intervals 22.228/44.422/49.998 ms, with
focus unchanged and acknowledgement snapshots up to 29 ms. This does not prove
a measured improvement over the X11 trial; the user reports a smoother feel.
The actual nested WL-1 mode reports refresh 0; Android still chooses 60 Hz,
while the actual parent eDP-1 active mode is 90.004 Hz.

A post-hut-fix user-directed six-second rapid-pinch trace completed, REA
`ev_9a54ce98235eb9ed7fc85237634683e9389710b8c7531108547bca6c70c8e9a7`;
private path `private-analysis/meego/zoom-trace-0318-20261014-182708/`.
Recent-ring intervals were 22.208/49.991/50.017 ms; focus stayed Meego,
post-trace dispatcher queue empty. Trace decoding/readback adds observer work,
and its recent SF ring overlaps collection end; no touch-to-photon latency
or improvement is claimed. Under-15-ms target remains unmet. Next investigate
frame waits and whether the verified native KDE output can replace the
refresh-unspecified nested compositor, with a reversible test before defaults.

## 2026-10-14: camera investigation, offline-only continuation

**Latest user instruction: no tests, no launches, no manual Deck input requests.**
They are away from the Deck and requested locating/investigating the camera code.
All runtime results below were collected BEFORE this restriction. Further work
in this phase is static artifact inspection and analysis of retained recordings.

The earlier direct-KDE-Wayland experiment verified Android at 90 Hz rather than
the nested compositor's 60-Hz fallback. Its active pinch recent-ring
median/p95/max presentation intervals were 11.289/22.231/22.248 ms. The user
reported **“still super choppy, Not fluid what so ever”**. This is not a verified
responsiveness fix or physical latency measurement. Sanitized recording details
are in `evidence/camera-display-comparison/camera-0318-user-trials.json`.

Offline native/DEX inspection located the camera and two concrete timing issues:

- `CCLayerPanZoom.ccTouchesMoved:withEvent:` at `0x80d66c` handles pan/pinch;
  pinch multiplies scale by current/previous finger separation. The 50-ms
  selected-item eligibility threshold is not a recurring camera throttle.
- `nativeTouchesMove` at `0x50c22c` rejects moves <=8.333 ms apart but updates
  its timestamp even for rejected moves. A burst can keep postponing delivery.
  Proposed narrow repair: rejected events should leave last-dispatched time
  unchanged. No such patch was applied. Existing delivery data does not prove
  this explains all stutter: only 10/291 recorded Android delivery intervals
  were <=8.333 ms, and those are not exact JNI move-entry/drop counts.
- The original `CADisplayLink._startTimer` schedules frameInterval/60 regardless
  of a 90-Hz display. This can contribute to uneven cadence; it is not proof
  that a timer change alone fixes zoom. Recovery-action overlap remains an
  unproven hypothesis, and native batch callback/previous-location handling
  still needs focused static tracing.

Full locations, evidence boundaries and next steps are documented in
`evidence/camera-display-comparison/pinch-code-findings.md`.

The opt-in 90-Hz timer APK was built/signed before the no-tests instruction,
but its attempted normal launch reached authorization and was cancelled.
`apk-revival-meego90-test.service` was stopped. No successful installation or
gameplay verification of that timer patch occurred. Candidate retained at
`~/.local/share/apk-revival/games/030613cbc63bd03786545999/work/0b7cbfb55d824b87801dda31324e16ae/restored.apk`,
SHA-256 `f2aad09b44f481ba5bb2fb361359eb063f62183d60946943b016bdd2771ba8ba`.

Restored the working Play target to `work/6966d68bf76e4f10b54241f7a27c99ff/restored.apk`
(SHA-256 `5b00554daae68fd65406b80777878fa03607ac4861da781a07051b29348ebaee`)
and removed the experimental timer profile override. The current village was
preserved; no older save was restored. Primary launcher binary is again the
verified 0.3.18 hut-fix build, SHA-256
`34492b49e8b244eda054cf8aa32b50f227f04865f5f81ee745dc90dd3e0ab1b8`.
Installed runtime helper was restored from
`backups/before-direct-display-20261014-183146/managed-waydroid.sh`
(the prior native-Wayland nested helper). No direct-display or timer experiment
was promoted as the default.

Uncommitted source experiments remain in runtime_setup/input_diagnostics,
managed-waydroid helpers, adapter/frame_pacing and associated tests. They were
prepared earlier; no tests/builds were run after the user's restriction.
Earlier checks recorded 35 runtime +9 diagnostics tests, and separately three
timer-patch tests passing. Those do not constitute live camera validation.
Keep these experiments separate from a release until their runtime behavior
is verified in a later testing phase. Preserve the untracked `error.log` and
private analysis; do not commit personal/proprietary artifacts. This checkpoint
commits only the camera findings, sanitized retained metrics and this handoff.

## 2026-10-15: camera repairs implemented in source, no execution

User requested “fix them” followed by “continue.” The no-tests/no-manual-input
instruction remains. Added the exact-hash/old-bytes native input rejection
branch repair in `meego/camera.py`; rejected moves now bypass timestamp stores.
Integrated the reviewed timer patch in `meego/frame_pacing.py` with conservative
active Android mode selection (90 only for active ~90-Hz modes, otherwise 60).
Adapter plans record repair revision/rate. Prepare invalidates pre-fix artifacts;
normal Play reads the current guest mode after runtime readiness, automatically
prepares a stale client using the same signing identity, and proceeds through
the existing data-preserving installation. Repeated Plays reuse matching plans.
Preparation tools must be available; the error names the Setup action if not.

Also fixed the static preparation-failure bug where replacing `p['restoration']`
before `prepare_data` succeeded could persist a new, incomplete artifact on
failure. The replacement is now published after successful data preparation.
Original APKs, current village, signing identity and installed binaries remain
unchanged in this pass. No service/runtime state or display settings changed.

**No tests, builds, installs, launches or measurements were performed.** Source
is implemented and committed for continuation, not promoted as a verified fix.
No new release artifact was generated. Previously written timer-only tests
are retained; regression coverage/execution for the input patch, active-mode
parser, auto-upgrade reuse/failure/cancellation and data/signature retention
remains pending. Physical zoom smoothness and the under-15-ms target are still
unverified. The earlier 90-Hz APK is timer-only and does not include this input
repair. See `evidence/camera-display-comparison/pinch-code-findings.md`.

The unrelated opt-in direct-compositor source experiments and their runtime
tests remain uncommitted and are not enabled by the camera repair. Keep
`error.log`, private artifacts and saves out of Git/release archives.

## 2026-10-15 05:00 PDT: authorized 0.3.19 trial

User asked **“ok so try it?”**, authorizing build/install/runtime testing again.
No manual Deck input was requested. The runtime was stopped after a reboot
(container service inactive, no ADB devices). Recovered the current Desktop
KDE Wayland environment from the user manager; no display name was assumed.

Passed: 14 targeted camera/timer/launch tests with the real original APK;
44 runtime/input-diagnostics tests; seven camera tests inside the actual
packaged binary; packaged version/TLS certificate probe; offscreen launcher
smoke. There were no failures/skips in these completed suites. One earlier
initial timer-only run skipped its private-APK test before its environment
was configured; the subsequent real-APK run passed it. Counts are 58 unique
source tests plus seven repeated packaged tests, not 65 independent tests.

Built the 0.3.19 binary by source repack under CPython 3.12, retaining the
existing licensed bootloader/Qt dependencies. This was not a clean PyInstaller
build. Installed binary SHA-256:
`9ceeede33ee5306b02bdf48635405dca20f595ba01950ab88ad7b7eb94afbdc7`.
Backup: `backups/launcher-before-0319-20261015-045709/`.
Current village/profile backup: `backups/before-0319-20261015-045606/`;
village SHA-256 `7b8ef1af705efd1a9097f5ce8296c0bc4625e2104c7890be6aa2b3e0fc61514e`.
The live save hash remained unchanged after the attempted launch.

An isolated copied-library build generated the signed/aligned 90-Hz input-fix
APK at
`private-analysis/meego/camera-0319-preparation/games/030613cbc63bd03786545999/work/fd08701e88144d59b35fdbc83a701ef0/restored.apk`,
SHA-256 `cc73b289ad0b1e360bb4f41c58bd14ca362589814f7270f45e718e3e3df6c4bd`.
It matches the working APK's signing certificate; only `lib/armeabi/libverde.so`
differs outside signature members. A real second build with injected
`prepare_data` failure confirmed the prior prepared reference and copied save
were retained. This APK has **not** been installed or launched in Android.

Normal Play request `b4145eb6a02f463dacdcb07542ffa595`, job
`662423350a18463eafa30e41a2da7754`, ran from installed 0.3.19 through the normal
UI worker under `apk-revival-camera-test.service`. The bounded attempt
**failed at runtime setup authorization after 110 seconds**, before compatibility,
camera migration, game APK installation or activity launch. The Android session
became ready during startup, but the required managed setup did not finish.
The authorization boundary was not bypassed. The runtime helper processes
were gone after normal failure cleanup; the launcher stays available.

The trial explicitly opted into the existing direct KDE display experiment;
no live camera/performance results were obtained. Afterwards the previous
native-Wayland nested helper was restored in the installed app and candidate
to preserve the user's prior default. The binary includes support for the
optional direct path, but the preserved helper does not enable it. Do not
claim the guest is now 90 Hz, game input is fixed on device, or the latency
target is achieved. A later normal Play needs successful runtime authorization
before the new game client can be installed and tested.

Local launcher candidate directory:
`dist/APK-Revival-0.3.19-camera-candidate/`. Generated donor executable backups
were removed only from this new candidate copy; all originals are preserved.
Metadata records the source-repack method and runtime blocker. This remains a
test build, not a runtime-verified release candidate; no public publish/push.
Sanitized receipt: `evidence/camera-display-comparison/camera-0319-validation.json`.

## 2026-10-15: user-present physical pinch follow-up

The user returned to the Deck, authorized runtime startup, and the normal Play
workflow installed camera repair revision 1 with the **60-Hz** timer. Verified
the prepared and installed Android APK hashes match:
`914e6581a2ec7a9c05ba568893f4603f3a386e9a675fbfb4f079d2962988680b`.
Meego's process was running, guest mode was 1280x722 at 60.000004 Hz on the
reported `wayland-1` socket. User reports **“feels much nicer”** and identifies
**mainly rapid pinch zoom** as the remaining issue. That is subjective feedback,
not a measured end-to-end latency improvement or proof of the sole cause.

User-directed eight-second physical pinch capture collected 287 unique new
presentations over 7.467 seconds of presentation timestamps (11 overlapping
read-only SF snapshots, pre-capture entries excluded). Median/p95/max intervals
were **22.213/50.005/260.970 ms**, with 54 intervals >33.34 ms. Focus stayed Meego;
post-capture snapshot had eight pending motions, maximum ACK wait 18 ms.
SF/ADB polling adds observer work, and exact gesture boundaries/physical
touch-to-photon latency were not measured. Receipt:
`evidence/camera-display-comparison/camera-0319-physical-pinch.json`.

Attempted the combined direct-Desktop-display + input-repair + automatic timer
comparison. Copied the opt-in direct helper into the installed app; the current
test launcher service environment already contains `APKR_RUNTIME_DISPLAY=desktop`.
Preserved the prior helper privately at
`private-analysis/meego/camera-0319-live/managed-waydroid-before-90.sh` and a
pre-comparison village snapshot (SHA-256
`291c0d1351ebea938e6fc01a210eb319438ef9f37c60d939b943577c7a194023`).

The first restart request was rejected because the game was still active;
this was a command sequencing mistake, not a newly discovered launcher bug.
Then normal Stop succeeded (`13dacf1a65bf4be8887ffffc4c2d005b`), followed by
restart request `cbd6024522e54555b9b0d12217c11606` (job
`0d3fb8dfba244cb886c642b20b9e3f4f`). Its startup marker reached ready, but the
request was cancelled between safe stages. A subsequent normal Play request
`e05af53043964ef1a55c2bcbf7fab996` timed out at managed authorization. No
combined 90-Hz game launch/comparison is established. Do not claim that the
timer changed to 90 or that the remaining camera issue was fixed.

REA host process capture is now blocked by `cleanup_incomplete`: live privileged
runtime processes have unreadable process ownership tokens (EACCES). Direct
sandbox DBus/ADB attempts also returned permission errors. No ownership/token
checks or security boundaries were bypassed and no unverified root processes
were killed. File-based **normal launcher requests** still work, and the library
lock is held by its running instance. Current question asks which actual Deck
screen is visible before another runtime action. Avoid repeated blind restarts.
If the direct trial is abandoned, restore the saved helper; the installed app
currently has the opt-in helper, while the local candidate directory still has
the previous native-Wayland nested default. Persist a Desktop display choice
through launcher settings only after a successful combined trial, not merely
through the transient test service environment.

## 2026-10-15: offline core completeness audit, no further game changes

The user reports **“screen works great”** and asked to compare actual original
and adjusted APKs and list missing features **before patching/installing**.
They clarified **no online/server-dependent features, just the core game**.
Current scope is audit/report only. No further game patch, build, install,
runtime operation, gameplay test or save edit was performed during this audit.

The current profile now references the 90-Hz input-repair APK, SHA-256
`cc73b289ad0b1e360bb4f41c58bd14ca362589814f7270f45e718e3e3df6c4bd`,
at `work/72427997dba94c33acddb930c0ae3a4f/restored.apk`, with a successful normal
activity-launch check at `2026-10-15T12:11:54Z`. The user’s positive screen
feedback is recorded separately from measured performance; no new live ADB
hash/display/presentation capture was obtained after REA's cleanup blocker.
The test service's Desktop display environment preference is still not a
persistent launcher setting. Preserve that earlier continuation item rather
than assuming reboot/new-launcher persistence was verified.

Byte-for-byte audit: original and adjusted archives both contain 741 entries,
no duplicate names, no added/removed non-signature members. Of 738 non-signature
members, 734 are unchanged and four are exactly explained by the recorded
restoration operations (manifest package ID, label resources, Info.plist
endpoints/identity, native transport/input/timer patches). Native library has
44 differing bytes, same size. Original TechTree and all Lua/scenes/images,
compressed textures and audio/sound-bank members remain byte-identical.
All five extracted backend rule sections equal the original tables. Evidence:
`evidence/meego-offline-core-apk-comparison.json`; full private per-member
inventory in `private-analysis/meego/core-audit/`.

Read-only source audit found missing **offline core mechanics**, rather than
content-transfer loss: production-building activation/stock/exhaustion cycles;
equipped tool production/time effects; commercial building rewards/boosts;
temporary and appearance-item effects; newborn/newcomer appearance/stat and
birthstone variety (factory hardcodes birthsign1 and base stats10); generic
achievements/progression/reward loops. Exact original genetics, effect
composition and balancing remain unrecovered. Existing host tests do not
certify all native menu/effect paths; Rabbit popup remains unverified.

Original tourist contracts identify other-player visiting Meego (remote job
name TOURIST, ownership/location checks, to_user_id travel API), outside the
requested no-social/online core. No independent NPC-tourist spawn contract
was recovered. Current saved-state observation found three permanent local
arrivals, six owned villagers and no other-owner guests. Arrival animations
were not checked. CHR work growth was originally associated with social
travel; supported permanent consumables can raise CHR locally, but there is
no local work alternative. Solo treasure/quest/dungeon features remain
unimplemented and are separately classified from required island systems;
do not silently label them complete.

User-facing full report with priorities, concrete file/line/native references
and scope limitations: `docs/MEEGO_OFFLINE_CORE_AUDIT.md`. Independent read-only
agents `tourist_parity_audit` and `offline_core_audit` completed the bounded
tourist/core-source checks; neither changed code, saves or runtime state.
Recommended implementation order when the user requests fixes: production
cycles and tool effects first, population/birthstone variety next, then effect
items/buildings and progression/reward loops. Keep explicit local policy
labels for formulas that cannot be recovered; do not reintroduce online
services or claim full original-server/game parity from archive identity.


## 2026-10-15: source-only gameplay fixes and requested GitHub export

User is away and requests no manual testing. The latest GitHub instruction
explicitly prohibits changes to the installed application or user data. All
work in this continuation is source-only, temporary-village tests and a fresh
temporary review clone. No installed app, Android package or real village was
changed. Version remains 0.3.19.

Implemented pending industrial production, equipped-tool and temporary-item
effects, future population variety and earned progression integrations. Wild
bush stocks are75 with one additive +55 standing-bush migration, preserving
harvested amounts and bank balances. Final-pickup wire projection clips only
the final finite-source response; original saved rates/fractions remain intact.
Simulation depletes all three wild node kinds exactly and releases all workers.
Native stock/rate rejection was NOT conclusively recovered: the wire repair
still needs a native-client trial and is not claimed as a proven device fix.

Seven new integration tests cover actual original-rule job assignment, last-unit
credit/depletion, new/standing bushes, all three industrial cycles, invalid
depots, equipped chainsaw yield and temporary boost expiry across serialized
restart/poll boundaries. They exposed and fixed stale active-job values after
equipping/removing tools and using boosters. All118 focused tests passed.
Full initial discovery ran377 tests: one release-note assertion, nine errors,
ten skips. The local release-note section heading was fixed. Eight errors are
sandbox-denied sockets; one is unavailable PySide6. A first supported-suite
filter missed unittest's failed-import wrapper and still reported that Qt
error; the corrected filter excludes the three unavailable test modules.
Source compileall and git diff --check passed. Full source feature status and
remaining limitations are in apk_revival/meego/OFFLINE_STATUS.md.

Unfinished agents did not produce commercial.py or treasure.py; no partial
module is silently activated. Native contracts were retained in the prior
solo-content documentation commit fd009b9. Commercial reward collection, solo
treasure/quest/dungeon sessions, special dungeon jobs, some scripted/infection
items and Photo Hut capture remain gaps. Local policy formulas are labeled;
no complete original-game parity or new physical latency claim is made.

GitHub export requirements: fresh branch deck-0.3.19-meego directly atop
df989d14740d4068b47ce7cafb4f89a1d1aebfdc; copy ONLY apk_revival/ and resources/;
exclude all APK/OBB/signing/save/log/cache files. Source found at
/home/deck/Apk-revival/apk_revival/__init__.py (0.3.19). Direct HTTPS git clone
failed DNS resolution. Authenticated GitHub tools can read/write the repo.
Fetched the exact signed base commit and all113 blobs/trees via that connection,
verified each Git object SHA (including the original signed commit), and cloned
the resulting shallow mirror into /tmp/apk-revival-deck-0.3.19-20261015 with
origin reset to the requested GitHub URL. No base history was fabricated.
Transfer scratch/evidence: /tmp/apkr-github-transfer/.

Root packaging metadata/tests/docs are intentionally NOT copied to the review
branch. Its pyproject remains0.3.7 by user instruction while Python reports
0.3.19. Reconcile metadata/release notes and port regression tests during merge
before attempting packaging. No installable candidate is certified and no
public release is authorized.

Supported-suite result:371 tests ran,362 passed and9 skipped; no failures.
Excluded modules were test_backend and test_meego (socket/live integration
boundaries) and test_opener_ui (PySide6 import). The118 focused gameplay
tests are included in those371, not additive. Initial private-APK builds in
the default suite succeeded up to sandbox-denied HTTP server startup; no
full runtime/packaging success is claimed.


### GitHub transfer completed

Branch: https://github.com/onlykappa/Apk-revival/tree/deck-0.3.19-meego
Commit: b2e07a353a111b4b3ca8fd3c195c69511d34fbc4
Message: Deck 0.3.19 local changes (ChatGPT Meego adjustments)
Only parent: df989d14740d4068b47ce7cafb4f89a1d1aebfdc
Tree:002f9776e311e0673ae251513da9650c53249fd8

Verified remote branch head, exact message/parent, complete staged-tree identity,
all76 copied file hashes and only75 allowed changed paths. The local review
branch tracks the same published commit and is clean. GitHub Git-data tools
performed the transfer because shell DNS blocked direct HTTPS Git access;
there was no claim that a raw git push command succeeded. Local pre-transfer
commit aa1ade8 had identical content and parent; GitHub-authored metadata
produced the published b2e07a3 identity, independently SHA-verified on download.

75 files changed (25 added,50 modified),3990 insertions/229 deletions.30 files
have only existing trailing-blank-line/newline differences compared to the
official base; exact source formatting was retained. No APK or personal data
is included. Exported Python compilation and all six shell-script syntax
checks passed. No installable build or release was published.

Latest local implementation commit:7b8b5a3. Full per-file review report:
DECK_0.3.19_GITHUB_HANDOFF.md (outside the export, per the only-two-folders rule).
Source status exported with the code:apk_revival/meego/OFFLINE_STATUS.md.
Next: merge review must reconcile root package version0.3.7 with Python0.3.19,
bring over tests, validate native last-pickup behavior on a separate authorized
trial, then implement commercial reward collection before further paid cycles.
Treasure/solo quest/dungeon work still remains; preserve those explicit gaps.
The installed application and actual village were not modified here.


## 2026-10-15: playable solo review delivered and branch updated

Published branch deck-0.3.19-meego now at
35452faf00b5af163d3219d8c9dec929fcb8a704, parent
b2e07a353a111b4b3ca8fd3c195c69511d34fbc4, tree
67a9d6af86784e5b3c88b35129f6720a1827526c. Message:
Port solo Meego adventures and earned offline rewards.
Only apk_revival/ and resources/ changed (22 files,2631 insertions,101 deletions).
94 copied eligible files byte-verified; no APK/data/keys/logs transferred. The
GitHub branch head,parent and full tree were re-read and verified. Review
clone /tmp/apk-revival-deck-0.3.19-20261015 tracks that same commit cleanly.

New modules: commercial.py, treasure.py, adventures.py, adventure_loot.py and
scripted_items.py. Root integrated native routes and atomic saving, fixed nested
JSON request parsing/duplicate-key rejection, and redacted malformed repeated
reward payloads. Away participants cannot work/use items/rename/breed at home.
Quest Portal waiting job49 is supported; Launch Dock other-player travel is
explicitly excluded. Questboostitems1186/1511 have native timed effect records
and local nonstacking earned-gold bonuses. Commercial rewards, original-stage
work, 15original themed loot IDs, treasure and owned cosmetic gifts are ported.

Native disassembly found and corrected a result-contract bug BEFORE publishing:
dungeon_results maps IDs to JMQuestResult(resource_rewards,bonus_resource_rewards,
item_rewards,points_reward,additional_bonus_rewards); summary.quest_results
uses different JMDungeonQuestResult names. Both item maps hold numeric counts.
The screen displays oneitem kind perrecipient; local loot honors that.

Unknown server balancing is not silently invented as original. Local policies:
commercial oneweightedroll perpaidfullhour, treasure1skull/opportunityperhour,
solo timed stages without fakeplayers, earned goldpercentage20/50boosts, and
1originalthemeditem after>=60sactualwork+activation+earnedgold. Source docs
COMMERCIAL_RULES.md,TREASURE_RULES.md,ADVENTURE_RULES.md,SCRIPTED_GIFTS_RULES.md
and OFFLINE_STATUS.md classify evidence and limits. Type2/3bugrewardgifts, cloud
infections and originalsocialquestcatalogue remainunsupported/unconsumed.

Validation:459 source cases ran,450 passed,9 skipped. Unavailable socket/Qt
modules were explicitly excluded, not passed.95 shipped regressions passed
on source and on installed bundledPython3.12 against CURRENT source, and95
passed from the exact temporary export clone. An initial test relocation had
wrong fixture parents; corrected before final passing checks. New tests live
under apk_revival/meego/regression_tests/ so Claude gets them despite the
two-folder export restriction; root default discovery loads them through
tests/test_meego_solo_regressions.py.

User returned to Deck and offered manual testing, then requested delivery before
limits. Scope frozen. Built and signature/alignment checked an ISOLATED
Android review APK with package ata.apktv.meego and endpoint port18766,
separate from main ata.apkrv.meego/18765. Created Desktop shortcut:
/home/deck/Desktop/APK Revival Solo Review.desktop
It runs the installed read-only Python/Qt bundle with current source via a
private review harness; this is not a new standalone launcher distribution.
The harness has its own Store and launch lock, and restores no personal save.
Review data/artifacts/logs:
/home/deck/Apk-revival/private-analysis/meego/solo-review/
The TEST village is explicitly funded (temple6,storagecaps,20skulls) for quick
manual tests; no funding is applied to the real village. Normal review Play
does not reset testprogress. Do NOT rerun prepare/test_prepare.py while playing.
UI offscreen smoke rendered1280x800 screenshot review-smoke.png; this was a
render smoke, not a unit test(the harnessrunnerprints NO TESTS RAN onclose).

Actual user-launched review reached successful Android activity at
2026-10-15T17:52:00Z and real login/tutorial/resource/job requests hit the
new backend. Runtime monitor reports succeeded. Current review APK hash
6adcffd9b87deeb8160b5b30dc768ccfa345521ea9b5449bdb837705abec572a,
signature_verified true, camera revision1/timer60(automatic conservative
selection; no forced unsupported90Hz). This establishes launch/request flow,
NOT a completed native dungeon or measured latency check.

Installed main binary hash remains
9ceeede33ee5306b02bdf48635405dca20f595ba01950ab88ad7b7eb94afbdc7.
Main installed app, APK and village were not replaced. The review Android
package and test Store are separate. Pending manual question asks user to
place/finish a Quest Portal in REVIEW village, assignadult and choose Turtle's
Grotto, report dungeonmap/error/missingportal. First question asks reviewisland
visibility. Await those answers before claiming native screenacceptance.
No further broad audits or agents; prioritize any confirmed native issue.

Root packaging metadata in export remains0.3.7 per original only-two-folder
restriction; Pythonversion0.3.19. Reconcile onmerge before a formalrelease.
No public release or merge performed.

## Follow-up: dungeon drag/drop and blank return (2026-10-15)
- Actual native job_data now decoded for dungeon source IDs; no save reset.
- Wire island name corrected to native `local`, leaving saved `village` intact.
- Review save retained 13 buildings / 2 villagers after blank-screen report.
- 96 focused regressions passed; native return confirmation pending.
- Known next tasks: validate native return; empty dungeon polling contracts;
  original bird variant 4 (currently rejected). Do not call the game feature complete.
- Published follow-up: GitHub branch deck-0.3.19-meego at
  8ac992d92a011f6dffe8d20ba4b390fd44060ce1. Remote source tree exactly matches
  fresh export index 2203047c25faa89af7693e9ecebc16f3611ed68b (five files).
- Installed launcher not replaced. Current-source isolated review loads these
  fixes when reopened; an already-running Python process retains old modules.

## Live Solo Review continuation: birds, finished portal, five testers
- User found Luma in expired dungeon; no earned work was recorded because old
  source-ID errors blocked assignments. No complete_dungeon_quest request seen.
- Finished dungeon packets now unload native stage rather than return expired
  active view indefinitely. Native portal/results screen still needs confirmation.
- Each signed egg identifier (0–5) can pay one skull once/session; old receipt
  retained and retries pay zero. This is a bounded LOCAL policy, not original
  server economics. Original mini-game variant 4 now accepted with own rules;
  all 1–11 require valid bundled timing records and same-variant session claim.
- Death/resurrection source present; added real-rule synthetic save regression.
- 100 focused regressions passed on host; syntax compilation passed.
- Private Solo Review bootstrap now prepares exactly five total villagers once,
  returning finished tester through normal claim and adding missing adults.
  Read-only copied-save trial passes: original input/buildings unchanged,
  five home villagers, repeated migration does not add more.
- Current launcher already running retains old modules. Requested full review
  close/reopen, then Play. Main app remains unmodified pending native review.
- Live review after restart has five people, returned Luma, accepted Portal
  job49, started a new Turtle trip, and successfully assigned job62/building42.
- Actual timer update omitted state; handler fixed to return already-settled
  state, validate supplied building type, and never recharge/recredit on retry.
- Turtle Topper371 explicitly has cost0/points_cost0 and no recipe. Resource
  purchase now supports explicit zero-cost shop items, retaining caps and
  rejecting missing prices or malformed paid recipes. Real-APK regression passes.
- Offline dungeon notice poll now returns recovered nested packet plus empty
  dungeon_notices; chat uses empty dungeon_chat_messages. No online feature added.
- Closed remaining initial-notices contract gap: original success block at
  0x91c33c calls intValue on response itself, so get_last_viewed_id returns
  numeric0 for no offline notices. No dictionary or fabricated messages.
- Staged source repack passed embedded (no source override) 105 regressions,
  certificate/version probe reports0.3.19. Main installation still unchanged.
- Source branch updated to94b6a4b96a881cecea44c248ab0a6e75648c5678;
  latest numeric-notice-ID follow-up not yet included in that commit.
- Additional native return gap: original job50 is post-dungeon/postquest,
  job type16. Finished participants now return home in that state, keep unpaid
  quest/results, and finished trips leave active_dungeons. This repairs older
  stranded finished participants on normal advance. Explicit claim still owns
  payout/idempotency. 105 host regressions pass after this transition.
- IMPORTANT: staged solo-candidate-2 predates this homecoming fix. Do not
  install it. Repack after the native reward/return check succeeds.
- Last published branch head69df6bbdfeb3b85c180b761c3789385bed931d6a;
  current homecoming follow-up is not yet pushed. Main binary remains unchanged.

## Main launcher promotion after native review (2026-10-15 22:32 UTC)
- Native review explicitly claimed trip2's five gold; immutable result receipt
  retained. Luma then joined Ice Bear trip3 and started original heater job53.
  This explains why a later read found her away again; her return was not lost.
- Final candidate: dist/APK-Revival-0.3.19-solo-candidate-final. Source commit
  9b880ff; 105 embedded (no source import override) regressions passed. Probe
  reports0.3.19 with certificates. Repack, not a clean PyInstaller rebuild.
- Installed ONLY the new main launcher executable via atomic replacement;
  original retained at /home/deck/.local/share/apk-revival-app-backups/20261015-223231/APK-Revival.
- New binary SHA256 bdf767dca33d7a268367e147e5950fc6771ba8d19347be235a99b95890c2812f.
- 17 protected main save/profile/APK files identical before/after, verified in
  private-analysis/meego/solo-review/installed-main-update.json (private local receipt).
- No Android APK reinstallation needed for these backend changes. No test
  villagers/supplies copied to main data. Existing camera patch preserved.
- User instructed to exit review and reopen regular APK Revival, then Play.
  Main Play verification still pending; do not claim it has run successfully.
- Pending physical checks: distinct eggs paying, Ice Bear second stage/end,
  death/resurrection UI. Native notice/chat contracts now empty/read-only,
  with numeric last-viewed ID0. No online features fabricated.

- Verified GitHub branch head c0fab767936520c248bfda0ce475644ab2ff0989
  includes all shipped code/tests/documentation from this fix pass. No APKs,
  saves, signing keys, private review fixture or logs were pushed.
- Additional live native evidence: Ice Bear heater job53 completed; native
  building36 timer polls at22:33:36/37 now succeed (previous Invalid state
  shape corrected). Full Ice Bear second-stage/end remains unverified.
- Review test is still running; user can finish it before switching. Updated
  main launcher is installed but main Play remains pending user transition.

## Storage / Thinking Rock follow-up
- Current user is still playing isolated Solo Review; main game logs remain
  at12:31 UTC. Do not mistake review evidence for a main-game launch.
- Actual Storage21 build job5 requests were rejected because original Storage
  state omits max_workers and housing villager_slots is explicitly0. Fixed
  construction fallback to1 worker; explicit worker limits remain enforced.
- Thinking Rock19 job20 earns research points, but get_research_progress was
  unsupported. Recovered original UI packet max_out/researching/progress from
  0x69ef9c–0x69f128. Implemented read-only display; original-cost explicit
  unlock remains authoritative. Cheapest eligible progress selection is LOCAL.
- 108 focused source regressions passed; catalog suite10passed/1skipped;
  compileall and whitespace checks passed. Native verification pending restart.
- Reference apk_revival/meego/RESEARCH_RULES.md. No new social features added;
  unrelated online gift request gaps remain explicitly out of scope.

- Storage/research candidate source7cfd224 built using embedded CPython3.12;
  all108 embedded regressions passed with no source import override. Version
  and certificate probe passed. Installed executable atomically; old app kept
  at /home/deck/.local/share/apk-revival-app-backups/20261015-224212/APK-Revival.
- New installed SHA25668281f22cc1757778ce925942cfc8a9291d64b63454926b11e4b4fe054614ed8.
  All17 protected main save/profile/APK files unchanged. Private receipt:
  private-analysis/meego/solo-review/installed-main-storage-research-update.json.
- Source branch pushed at a70995b2c5cb3125736599827ca0e6de2cea5ef2; only
  source/docs/tests under apk_revival exported. No personal files or APKs.
- User asked to restart complete Solo Review launcher, assign available adult
  to existing Storage21, wait45sec, and open Thinking Rock19. Awaiting native
  confirmation. Main launcher is installed, main game launch still unobserved.

## Ice fishing / Thinking Rock upgrade follow-up
- Native Storage21 construction succeeded (state1, builder idle); user confirmed.
  Thinking Rock get_research_progress succeeded on native client.
- User reported orange fishing circles/holes closing/no rewards and Thinking
  upgrade reopening as Loading. Read-only save: Ice trip3 stage2,58 staged gold;
  Thinking Rock19 upgrade state10 initially, then state11 after real builder.
  Asked whether Loading persists after close/reopen now completion is saved;
  do not infer a separate upgrade bug without that result.
- Confirmed fishing deadline bug: source expired after first10sec although4/5
  catches remained; native log had repeated building updates ~1.1sec apart.
  Deadline now covers all stock/partial work, repairs legacy timers and clears
  abandoned-hole timers without refilling stock or adding gold.
-110 focused regressions passed before final immediate-idle assertion addition;
  package verification pending. No invented immediate fishing payout: original
  gold remains in trip record and normal final claim owns credit/idempotency.

## Discovery / Doctor category follow-up
- User confirmed Thinking Rock reopens after upgrade. It showed Next Discovery
  but no actual discoveries; Accessories remained grey. Saved review research
  balance62034, cursors empty. Original Doctor locks on is_researched and
  Accessories sort_type4; original Nose Bone387 requires temple4/research588.
- Added automatic original-cost discoveries while a living home researcher is
  assigned to a completed Rock. Local deterministic order cheapest eligible,
  then numericID; retains original prerequisites/temple gates. Normal helper
  debits research points and records cursors/receipts once. Unlocks recipes,
  does not grant/equip purchased items. No worker means no spending, display
  reads remain read-only. Construction cannot keep generating research work.
- Copied-review-save dry run (no write) discovered16 recipes for59737 points,
  including five accessory recipes. This reflects funded test-village balances,
  not original starting economics or a promise of free accessories.
-114 focused source regressions pass; catalog10pass/1skip, compileall and
  whitespace checks pass. Packaging this together with fishing and late-timer
  fixes before updating main. Native verification pending restart/assignment.

- Built discovery/fishing candidate with embedded CPython3.12;114 embedded
  regressions passed (no source import override), certificate/version probe
  passed. Installed only executable with old binary backed up at
  /home/deck/.local/share/apk-revival-app-backups/20261015-225251/APK-Revival.
- Installed SHA256349acbbd6f7eb7890c155ea4f7e467e70e77c9531402d2b763e190a0d5ebed0f;
  all17 protected main save/profile/APK files unchanged. Private receipt:
  private-analysis/meego/solo-review/installed-main-discovery-fishing-update.json.
- Source branch pushed and pending verification at
  0ac19ee97da894416b5a1c36a5bdb1181a2b9e82, source/docs/tests only.
- User asked to restart complete Solo Review launcher, assign adult to Rock,
  wait15sec then reopen Doctor Accessories. Native discovery confirmation
  pending. Fishing orange-circle outcome also pending fresh native trial.
- Read-only save now confirms Ice trip3 CLAIMED with58 gold, demonstrating
  original stage transition/fishing work/final claim path executed.

## Level6->7 audit and display correction
- User reported inability to level6->7. Asked whether Temple Upgrade or island
  number/bar; no answer yet. Investigated both without granting resources.
- Original Temple6->7 costs90000stone/180000wood/2200gold. Review wood146161
  was short33839; no failed Temple upgrade request in recent logs. This is a
  legitimate affordability requirement, not evidence of broken construction.
- Confirmed independent display mismatch: village/user level forced to Temple6
  while affluence25459's bar used23640->25610. Village level now uses that same
  LOCAL milestone schedule (review maps13); Temple remains6 and gates unchanged.
  Exact original-server XP schedule remains unrecovered; see LEVELING_RULES.md.
- Added real-rule tests of ALL Temple upgrades1->14, retained levels during
  construction, original-cost shortages/no skipped states, and independent
  village6->7 display crossing without changing resources/Temple/research gates.
-117 shipped regressions pass;40 related local progression/simulation/catalog
  tests pass. Initial related command had test import-path error and stale
  Turtle Topper rejection expectation; corrected invocation and updated the
  outdated expectation to original explicit zero cost. No hidden failed tests.
- Corrected tests/test_meego_progression.py and tests/test_meego_catalog.py are
  local root tests, not exported under the two-folder-only source instruction.
  Shipped leveling regressions remain under apk_revival/meego/regression_tests.

- Leveling sourceba37aee built;117 embedded source regressions passed with no
  source-import override. Certificate/version probe passed. Installed only
  executable, backup at
  /home/deck/.local/share/apk-revival-app-backups/20261015-230050/APK-Revival.
- Installed SHA256d35834e91344cf927280e2a7486b529060a78f185fc9ddf37a3ab00d74ba7ae8.
  All17 protected main save/profile/APK files unchanged. Private receipt:
  private-analysis/meego/solo-review/installed-main-leveling-update.json.
- Source branch pushed and verified at2f056fdd708484f7e59d39e167ac4d9bd9edd57e;
  all shipped changes are source/docs/tests under allowed apk_revival folder.
- User instructed to fully restart Solo Review and compare level/bar, with
  Temple7 original wood requirement intact. Physical confirmation pending.
- Prior discovery follow-up now has native saved cursors16, demonstrating
  automatic discovery executed after restart. Accessories UI purchase still
  not explicitly confirmed by user.


## Turtle Topper cache fix and requested fresh main island (2026-10-15)
- User confirmed village level14; leveling display is physically verified.
- Turtle Topper authoritative ownership was not duplicated: logs reject repeat
  removals from old wearers. Original equipment callbacks use merge options27,
  which omit remove-untouched bit4. Sending an empty map left a cached worn hat.
- Native wire projection now sends explicit null deletions for absent known
  inventory/equipment IDs, including old cached ghosts; saves remain unchanged
  by projection. Native strong-dictionary binder0x98a5e0 explicitly deletes
  null records. Evidence saved privately in equipment-*-annotated.txt.
- Source commit e03dbc6.118 source +118 embedded regressions PASS, including
  capped purchase, equip/remove/transfer, duplicate rejection, save roundtrip,
  and native deletion projection. Physical appearance confirmation pending.
- Repacked candidate dist/APK-Revival-0.3.19-equipment-candidate from installed
  licensed distribution (not a clean PyInstaller build). Version/cert probe PASS.
- Installed executable SHA256
  59cfadba568220ec54e52c806c26828b363332884d06dc5e772fca273c710ee5.
- User requested fresh main island and confirmed all windows CLOSED. Clarified
  starting roster; user accepted3 playable villagers. Main save replaced with
  clean no-bonus starter Miko/Luma/Yata, level1 Temple1, zero resources/skulls,
  no test inventory, discoveries or quests. Fresh State startup/reload and
  12-second advance tested on temporary copy before replacing live save.
- Save-only replacement, no Android reset, APK rebuild/reinstall or data clear.
  Other16 protected main files (profiles/originals/other games) unchanged, and
  Solo Review save unchanged. Backup of old main save and executable retained
  at /home/deck/.local/share/apk-revival-app-backups/20261015-161050.
  Private operation receipt: solo-review/installed-main-equipment-fresh-update.json.
- GitHub deck-0.3.19-meego pushed and verified at
  770cb8a73ded63f7493f8e3cb71faccc17a8fb59. Only3 allowed source/test/doc files
  exported; no saves/APKs/private fixtures. Source blob SHA1 verified beforepush.
- User instructed to use NORMAL APK Revival.desktop -> The Meego Play, not
  isolated Solo Review shortcut. Native main startup confirmation pending.
- Normal main continues using ata.apkrv.meego /port18765 and existing90Hz
  camera-patched working APK. Review remains ata.apktv.meego /port18766.


## Separate v0.3.8 launcher merge candidate (2026-10-15)

Location: /home/deck/Apk-revival-merged-0.3.19-v0.3.8
Local branch: merge/launcher-0.3.8-meego
Commits:812f5a2 (launcher merge/runtime access),87d709b (portable export packaging).
Original /home/deck/Apk-revival checkout and installed0.3.19 remain untouched.
The user is playing Meego; no game/runtime was stopped or save changed by us.

Completed:
- Pinned upstream releasev0.3.8 commit775d190baf4477e3e1491435b1e0f77fb1add98d.
  Git shell network DNS failed; GitHub API supplied original base blobs and the
  release patch, with original Git blob hashes verified before3-way merge.
- Resolved overlapping UI/service/styles/version changes, retaining upstream
  design, all local runtime recovery/input capture/new-village actions and APK
  inspection. Candidate version0.3.20; all35 Meego source modules byte-identical
  to current tested game code, including camera and recent gameplay fixes.
- Corrected wrapped-label size policy after offscreen screenshot exposed long
  title/package text stretching the details panel1021px across a378px viewport.
  Regression reproduced failure before fix; both1280x800 and1000x650 now pass.
- Added optional root-owned fixed-command runtime helper and one-time Setup
  installer. NOPASSWD rule permits only probe/preflight/mount/start-container/
  post-start for the invoking user and main profile; NOSETENV, no wildcard/shell
  access. Validates ownership/account/paths/syntax, refuses unrelated files, and
  rolls back on validation failure. No runtime restarts during installation.
- Desktop and Cage startup use noninteractive helper only when installed; absent
  helper keeps existing graphical authorization. Existing helper failure reports
  an error without falling back into more password prompts. Recovery preflight
  uses the same helper. See docs/RUNTIME_ACCESS.md for scope and removal.
- Found packaged portable export lacked physical source files at synthetic PYZ
  module paths. Candidate repack and clean-build spec now include only project
  .py sources; packaged export regressions pass. No private game data bundled.

Validation:
-124 source launcher/runtime tests PASS. Initial mixed source/frozen test
  harness produced2 export errors; corrected source import setup and repaired
  actual missing-source packaging before final packaged validation.
-245 PACKAGED tests PASS, including118 Meego gameplay regressions,124 launcher/
  runtime checks and3 metadata checks. No source override for packaged run.
- Offscreen packaged real-widget preview PASS with temporary imported APK data;
  no Play or runtime commands. Screenshots at build/merged-library-1280x800.png
  and build/merged-setup-{1280x800,1000x650}.png. Main data not used as a Store.
- Archive staging/extraction and real child version/certificate probe PASS via
  original installed updater with an isolated temporary home; NO installation.
  Initial archive assertion incorrectly prohibited the existing self-authored
  Tap Quest demo APK; corrected to explicitly allow and validate only that
  fixture. No Meego APKs, saves or signing keys are in the candidate package.
- Python compilation, shell syntax, real visudo policy parse and git diff checks
  PASS. Privileged installation/real password-free startup NOT tested.
- Logs/receipts in build/{source-launcher-tests,packaged-tests,preview-test,
  archive-test,build}.log and build/merge-verification.json.

Artifact:
- dist/APK-Revival-0.3.20-merged-candidate/ (separate one-directory app).
- dist/APK-Revival-0.3.20-linux-x86_64.tar.gz (139MB), SHA256
  4fb1d074ab6e1f511faa9fd7358bc38350e240848ef8bf2fcf8b469d3a91db0f.
- Candidate executable SHA256
  503541ec167b20c19a02d089fec70950a6dc1ebafc8bc6809e85de16e7ed4f09.
- Uses existing licensed Python3.12/PyInstaller distribution and repacked
  project modules, NOT a clean PyInstaller build. Clean spec updated but not run.
- Installed app still0.3.19, SHA256
  59cfadba568220ec54e52c806c26828b363332884d06dc5e772fca273c710ee5.

Blocked/pending:
- Sandbox sudo cannot elevate (`no new privileges`; host UID ownership is also
  remapped). /etc/apk-revival/runtime-helper does not exist; no system policy
  was installed or altered. User must authorize one-time setup on host.
- User can continue playing. Only after they finish/close Meego and APK Revival
  should the candidate replace installed app. Preserve current live save, APK,
  all settings and signing keys; do NOT create another fresh island.
- Then use Setup -> Enable password-free startup (one administrator prompt),
  cold-start main Meego and confirm no repeat password prompts, retained data,
  controls/camera, second launch and later reboot recovery. Do not report this
  pending host check as passed.
- No public release, GitHub main merge or remote branch change was made in this
  task. Prior deck-0.3.19-meego GitHub branch remains770cb8a; this integration
  branch is local pending review/host trial.


## Urgent resource tails / infant sentinel follow-up
- User reported final1 items stuck for trees/bushes/rocks,596523:14:07 baby
  countdown, and requested2 base resources per trip. User closed game/launcher.
- Read-only main save showed the backend collecting the last node unit and
  removing the node, while the original merging client retained old objects.
  Added512 bounded persistent depleted-node markers and explicit wire nulls.
  No extra reward; skips currently reused IDs and never edits dungeon maps.
-596523:14:07 is INT_MAX seconds. Offline ELF/LLVM confirmed the native NSDate
  conversion requires NSDecimalNumber (relocation0xbf5d20, code0x83a880); aging
  wrote integral last_update values, so the native date stayednil and
  JMJob.expire_date selected distantFuture. Wire now emits integral last_update
  as decimals, preserving saved birthdays and fixed whole-second deadlines.
  Baby2h/child10h local policy unchanged, with parent release/growth tests.
- Requested local balance: stone/wood/food jobs16/17/18 have base2; research1
  remains. Existing strength/tool/boost modifiers and60 delivered-unit stat
  threshold remain; no retroactive reward or save reset.
- Source4a14b55 cherry-picked into merged branch as7e377f6.121 shipped source
  regressions PASS,52 related aging/trip/simulation/skill tests PASS. Updated
  legacy expected harvest totals for intentional base2. First related command
  named a nonexistent test_meego_harvesting module; corrected invocation.
-248 packaged regressions PASS in dist/APK-Revival-0.3.20-harvest-candidate,
  no source override. Prior merged candidate/archives retained under initial/
  before-harvest names; use current canonical tar or harvest-candidate only.
- Installed FULL0.3.20 app directory with data outside it untouched. Exclusive
  launcher lock acquired, previous app directory retained at
  /home/deck/.local/share/apk-revival-app-backups/merged-harvest-20261015-201423/
  APK-Revival-app. All17 protected files (including current village and APKs)
  hash-identical before/after. Installed SHA256
  d7a11c893a6104512cdd968799b940d2d3b6c86b15564d366dd93dccc8da4573.
  Receipt: build/installed-harvest-update.json. Version/certificate probe PASS.
- Gameplay source pushed to deck-0.3.19-meego at
  df0ff6eec648e1c122a793b0d4e7eaeea491dad7. New full integration branch also
  being exported with code/build/tests/docs/handoff; no private APK/save/key/
  raw native traces are published.
- User instructed to open normal0.3.20, Setup -> Enable password-free startup
  and complete ONE host admin authorization, then Play. Sandbox cannot elevate,
  so root helper remains UNINSTALLED until that host action. No promise of
  password-free startup verification until installed and cold-start observed.
- Native timer/final-node display confirmation pending. Lowsee's birthdate was
  preserved, so elapsed offline time may already make her a child on next Play.
  A fresh baby's finite nursing countdown remains the strongest physical check.


### Final publication / verification
- Full source integration branch deck-0.3.20-launcher-meego published at
  ba15e6b977f3dc1679af71606ffdfb1f93e42f1c. Verified all112 changed source/build/
  test/doc file hashes in the remote Git tree after push. Upstream LICENSE kept;
  private raw evidence, APKs, saves and signing keys excluded.
- Concise next-AI entry: docs/AI_HANDOFF.md on that branch. Core game patch-only
  branch deck-0.3.19-meego remains atdf0ff6eec648e1c122a793b0d4e7eaeea491dad7.
- Final248 packaged checks and121 shipped source regressions PASS;52 aging/trip/
  simulation/skill plus48 effect/production/wire/ecology checks PASS (100related).
- Final hotfix archive staging/extraction + actual child version/certificate
  probe PASS using the previous0.3.19 updater with a temporary isolated home.
  Canonical tar SHA256
  3b3741d376629043bd5f722bf375dcba9baf0d0f9d99c43def3abec4d9d76b37.
- Installed0.3.20 executable stillmatchesd7a11c...a4573. No additional installed
  code or data changes after the verified application replacement.
- Host root helper NOT installed by sandbox. One-time Setup authorization and
  physical baby timer/node-tail/cold-start confirmation remain pending.


## October 15: finite baby timer confirmed; fullscreen follow-up

The user confirmed Lowsee's normal timer and child transition. A photo showed
Meego in a decorated KDE window above the visible desktop panel. Added an exact
package-scoped transient KWin fullscreen request before local Waydroid activity
launch, with unload on stop and a nonfatal fallback. No save edits or permanent
desktop rules. New game_window tests execute real JavaScript against synthetic
windows and mock D-Bus lifecycle; actual compositor behavior remains pending
normal Play because the sandbox cannot reach the host bus. Offline simulation
already catches up from saved dates, with a 24h cap on work/food. See AI_HANDOFF.

Verification: 253 packaged checks passed; five fullscreen checks passed, with
real JavaScript execution and mocked host D-Bus boundaries. Packaging repack
succeeded. Native fullscreen behavior is pending the user reopening Play.


## Respawn and host startup follow-up

User's old shared15min resource clock could rotate one kind to45min. Added
one-per-kind checks with unchanged site validation, pool caps, stock sizes,
no offline backlog and deadline-preserving legacy migration. Ten ecology checks
and a private original-rule integration check passed; a copy of the live save
also proved safe replenishment without writing it. Latest reopened island had
full4/3/3 pools via native startup recovery; no manual resource refill applied.

One-time setup initially reported success but Play failed sudo-n. Moved only
the dedicated rule after SteamOS wheel configuration and added an uncached
non-root effective-access probe with rollback. Corrected Setup installer was
atomically installed in the existing app; the user ran it and normal Play
opened. Host setup now verified at least one cold startup, reboot pending.

Game opened after a black startup window but was not fullscreen. Logs showed
the initial default nested Cage path, not the previous direct KDE display.
Made direct supplied KDE socket the cold-start default, retaining socket
validation and explicit nested/Gaming Mode behavior. Stop now closes only
owned runtime sessions after stopping the game/backend. Candidate is
0.3.20-respawn-stop-candidate; actual new fullscreen/Stop behavior pending.

All269 packaged regression checks passed on this candidate, including the
new ecology, effective-access rollback, display selection and Stop lifecycle
checks. Packaged test logs: build/respawn-stop-packaged-tests.log.

Installed respawn/Stop/direct-display candidate at20:41 with all17 protected
files hash-identical, including the live save and original/prepared APKs.
Version/certificate probe passed; user physical feedback pending. Installed
SHA256 a8c9a3016ccc5068e40e5cff2a5227acdb0f0c89fbc813cd53e9db3107b6ebdb.


## Building moves, Topper and Rabbit card follow-up

Move failure675 was the native source location, while the building's realID
was16. Corrected only the move endpoint's resolution; identity, jobs, balances,
placement validation and upgrade/delete contracts remain intact. Reproduced the
exact failing request on a memory-only copy without changing the live island.

Topper was mechanically active (saved rate3.06 and backend cooldown rejection),
but native cooldown expects absolute NSDate rather than remaining seconds.
Added wire-only decimal absolute expiry and missing native buff indicator
records, retaining existing backend math and save format. Core26 checks pass,
including repeated moves, expiry, restart, single1.5x math and icon migration.

Rabbit original metadata/artwork is present. User says villager's own card.
None of the current villagers actually carries Rabbit4; they have only one
stone each, and original UI draws two slots. Missing second-slot artwork is a
supported hypothesis, not a verified final fix. Awaiting which villager and
left/right slot; do not fabricate traits or reset data. See AI_HANDOFF.md.

Installed the move/Topper candidate at20:54. All305 packaged tests passed,
all17 protected files stayed hash-identical, version/certificate probe passed.
Native physical confirmation and Rabbit slot detail remain pending.


## User-requested five-minute resource supply

Reduced per-kind replenishment15min->5min, still one rock40/tree30/bush75
per due check with safe observed sites and original4/3/3 caps. Both previous
15min policies migrate using their existing cycle start (next_due minus600),
without repeated-poll postponement, balance refills or offline backlog. Eleven
focused tests passed, including exact299/300s bounds and both old policies.
Candidate0.3.20-five-minute-candidate; physical300-second check pending.

User then requested an absolute ceiling of6 trees,6 bushes and6 rocks.
Centralized that requested cap for both native startup place_resource requests
and timer spawning; removed the conflicting original3/3/4 rule clamp. Safe
site checks remain unchanged, and existing stocks are not deleted/refilled.
Tests exercise repeated due cycles at saturation, native seventh-spawn denial,
independent counts for all types, and recovery back to6 after a depletion.
Final candidate:0.3.20-five-minute-six-candidate.

Installed the5-minute/6-cap candidate at20:59. All307 packaged tests passed;
all17 protected files remained hash-identical; version/certificate probe passed.
Native wall-clock five-minute respawn observation remains pending.


## Green-check relocation lifecycle and orientation2

The position-only fix moved the save but not the native map object: first move
saved16.location2765, second still sent675. Native uses destination tile IDs
and does not observe in-place location changes. Added per-move model rekey,
explicit old-model deletion, destination creation, referenced worker/depot and
school-key remapping, stable local reward/progression identities and collision
rejection. No bulk save migration. Native1/2 facings plus legacy0 are accepted
across placement/movement/ecology; previous high1 rejected real orientation2.
Source31 original-rule checks pass. Current-island memory-only check proves
old16 deletion/new2391 creation with facing2 and unchanged real save bytes.
Candidate0.3.20-relocation-candidate. Native screen validation pending.

Optional per-timer in-game Skip button feasibility explained; not implemented
in this hotfix, and no global fast-forward/aging or food changes were made.

Installed at21:11 after the user closed both apps. All328 frozen packaged
tests passed; all17 protected save/profile/APK files remained hash-identical.
Installed version/certificate probe passed. SHA256:
9d811f7ff4ce7e609fa25aec5c20be604d96eae5df5db339da343fcb9fc978c5.
User asked to verify two consecutive moves plus both facings on the screen.
