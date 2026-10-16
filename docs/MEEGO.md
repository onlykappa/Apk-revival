# The Meego: first real-game adapter

Supported input is The Meego v1.32, original package `ata.squid.meego`, SHA-256 `030613cbc63bd03786545999c3590456a264796866127898928a4d59988d29a2`. Other APK versions do not silently use these patches.

This is the local-backend path. Standalone offline APK and separate rebuild workflows are not implemented for Meego. The native game and assets remain in the APK. The earlier experimental responder was self-authored from observed client expectations and recovered bundled rules; it is not recovered original server code or full feature parity.

The [2026-10-15 offline-core audit](MEEGO_OFFLINE_CORE_AUDIT.md) compares the
actual original/current APKs and lists missing local gameplay mechanics.
Bundled content is preserved; this does not yet establish a complete offline
island game. Online accounts, real-player visits and payments are excluded
from that audit's requested scope.

## Use it on the Deck

1. Install APK Revival with your existing initialized Waydroid installation. Play manages runtime startup, readiness and the current ADB connection; routine launching does not require opening Android Settings or entering terminal commands. Waydroid and compatible ARM translation remain runtime dependencies, as described in [APK_OPENER.md](APK_OPENER.md).
2. Add the original `The+Meego_1.32_APKPure.apk`, then Prepare. The app handles patches, alignment, signing and private local-service configuration.
3. Play. The separate Android application is named **Reviv**, package `ata.apkrv.meego`. It leaves the original game and earlier Local/Fresh installs intact. The launcher starts an owned loopback backend and checks Android-to-host reachability using a fresh nonce through ADB reverse.
4. Game options contains Backup Save, Restore Save and Export. To import an earlier village, attach exactly one `village.json` as a **Save file** before preparation. It is copied only if the launcher has no current village save; an existing launcher save is never silently replaced. Do not expect the older Meego launcher's host save to be adopted without selecting it.
5. To test offline gameplay, choose Game options > Advanced > Test offline now. Follow the guided confirmations while interacting with Meego in Android. The test temporarily blocks external guest connections and restores only its owned rules when finished or cancelled.

Waydroid must support the original 32-bit ARM native library, through compatible ARM support/translation where necessary. Android version, rendering and native bridge behavior need testing on the target device. A package can be signed successfully and still fail to play.

## Exact reviewed changes

* `lib/armeabi/libverde.so`: same-length ARM instruction patches at offsets `0x8e32f0` (`0xe1a05003` → `0xe3a05000`) and `0x8e330c` (`0xe59b8008` → `0xe3a08001`). These select HTTP with an explicit local port. Each operation checks the entire member hash and original instruction bytes.
* Compiled Android manifest: same-length package substitution, avoiding signature conflicts with earlier installs. Version is preserved. The app label is changed to Reviv with same-length compiled string replacements.
* `assets/Info.plist`: local endpoint and identity fields route to guest loopback. The launcher creates owned ADB reverse forwarding to its host loopback service. It never assumes Android localhost is the host.
* `assets/TechTree.plist`: buildings/items/jobs/point-store rules are extracted into private working data. No recovered game-rule table or proprietary asset is committed or shipped inside the app.

All archive changes are explicit, hashed and reviewable under Advanced. Original files are read-only copies. Failed patch preconditions preserve the previous prepared artifact. Preparation generates a fresh signed APK; it does not use or distribute the earlier private signing key.

## Local service scope

The service supports local resource spawning/gathering, building placement/movement/upgrades, workers and construction timing, local currency purchases, provisional breeding/aging/food simulation and persistent village state. It also provides owned newcomers, productive-work stat growth, supported permanent stat consumables and Skool classes. The balance choices and recovered client contracts are separated below. Unsupported requests return explicit errors. No real payments, original accounts or upstream network calls are performed.

Quest chains, social/multiplayer features, treasure behavior, original economic balance and some visual effects are incomplete. The API can persist an action correctly while the native UI handles it differently. Android checks are therefore necessary.

The earlier user reported village rendering, menus/zoom, resources, building purchases/upgrades and level-four temple progress saved on Steam Deck. Those observations concern the earlier package and transport. They do not certify this new client, package, signature or ADB-reverse configuration.

## Guided verification evidence

The test records cold launch and visible village/menu interaction, a successful new building-action request, saved state, restart of the game and backend, visible loaded progress, deliberate service failure and recovery. Human confirmations are explicitly labelled user observations because the native OpenGL UI lacks reliable text automation. Host-side HTTP results alone never satisfy the gameplay checks.

Verified Offline requires every check, enforced IPv4/IPv6 guest restrictions, negative external probes, an unchanged prepared artifact and successful cleanup. Unavailable root/firewall capabilities refuse certification. Cancelling records an incomplete test. The scope excludes untested mechanics listed above.

## Earlier isolated build-environment limits

The original isolated build environment had no Binder devices or Wayland session, and its root capability bounding set was empty. Installing userspace Waydroid could not supply the missing host privileges/kernel devices; there was also no `/dev/kvm` for a hardware-accelerated emulator fallback. Those early host checks did not test Android gameplay. Later Steam Deck observations and their limits are recorded in [TOUCH_DIAGNOSTICS.md](TOUCH_DIAGNOSTICS.md).

See [MEEGO_TEST_RESULTS.md](MEEGO_TEST_RESULTS.md) for observed tests and the remaining Deck checks. Private diagnostics and saves remain outside GitHub.

If the process is forcibly killed or Android disconnects during cleanup, networking may remain blocked in that guest. In-progress verification records retain the exact owned chain and serial under the private game directory. Use the existing [verification recovery instructions](VERIFICATION.md); never flush unrelated firewall rules. Normal cancellation, closing and termination request orderly cleanup.



## Fresh village without testing bonuses (0.3.14)

New local villages start with two Meego, the level-one temple and no resource or crystal-skull bonuses. Existing saves keep their earned balances. Game options > New village (no bonuses) starts over with an automatic backup of the prior village; it preserves the Android package and installation. Exact original server starting values have not been recovered, so these local defaults are not certified vanilla Meego. Construction/gathering/aging balance and unsupported features remain provisional as described above.

Housing now includes the original temple's five villager slots and capacities retained by building upgrade states. The previous completed-huts-only calculation incorrectly blocked starter breeding. Error responses use the native failure callback. Visual hut completion/indicators, continued drag/camera lag and untested mechanics still require device checks; passing host simulation tests alone does not establish full gameplay parity.

## Current local balance and progression

The original APK contains the game client and rule tables, but its retired server's full economic rules have not been recovered. These changes provide an explicit local restoration policy. They do not establish the absolute full game experience, exact original arrival rates, original stat-growth coefficients or complete original-server parity.

| Mechanic | Current local behavior | Evidence boundary |
| --- | --- | --- |
| Rock, tree and bush stock | Each new node holds **40 rock**, **30 wood** or **20 food**, respectively. These are total remaining node supplies, not amounts awarded on every visit. | Locally chosen stock sizes. The original client displays the node's `count`; uniform 500 was an earlier local default. |
| Gathering | Baseline **one resource per completed 12-second trip**, comprising eight seconds of gathering and four seconds of travel. STR affects harvesting yield; INT affects Thinking Rock yield. Fractional yields persist across updates and restart. | The native client consumes `gather_rate` as amount per completed `trip_time`, not amount per second. The 12-second baseline and stat-to-yield coefficient are local choices. |
| Work stats | **One STR point per 60 delivered harvesting resources**, or one INT point per 60 delivered Thinking Rock resources. Only the amount actually delivered counts; blocked or depleted trips grant no progress. | Local growth threshold and mapping. Original tooltips say stats improve through relevant work; original server coefficients are unknown. |
| Newcomers | At most **one owned adult every six real hours**, when living owned population fits housing and the population limit. First use of this policy starts the timer without adding anyone immediately. An overdue offline interval adds at most one; full capacity discards that opportunity rather than building a backlog. | Six-hour cadence, adult stats and eligibility policy are local. Owned villagers, separate guest models, housing slots and the original client ceiling of **25** are recovered contracts. |
| Skool | An eligible adult teaches available children for **one hour**. A completed local class awards each participating child up to **+1 INT**, within the local cap, and a report card. Collecting reports again does not award the point again. | One-hour duration and teacher/student job fields are bundled rules. Guaranteed success and +1 INT are local policies; original grades, subject selection and reward formulas are unknown. |

Living owned travellers reserve their home beds for newcomer capacity. Native dead villagers use no permanent slot but their saved records remain. Guests are other users' temporary travellers and do not count as newly owned population. Real social visits and Launch Dock travel rewards remain unsupported; they cannot be claimed as restored charisma progression. Food or mood gates for original immigration have not been recovered and are not invented as recovered requirements.

Stats are the villagers' base STR, INT and CHR values, not a spendable skill-point wallet. The native stat buttons explain their meaning; no point-allocation API was recovered. Equipment bonuses stay in equipped item properties so the original client adds them once for display. Supported owned permanent self-target consumables apply their original `add_strength`, `add_intelligence`, `add_charisma` or `add_random_stat` properties. Equipment, temporary boosts and unsupported village gifts do not silently become permanent stat upgrades. Original consumable descriptions state a positive increase cap of 1799; local work/class gains use the same limit, whose original applicability to work is unknown. Existing above-cap values are preserved.

Report cards use the recovered `{game_state, report_cards}` response wrapper. Each successful card contains `success`, numeric `stat_count` and string `stat`; the native client inserts that string directly into its display. The local class reports `INT`. That label is compatible with the display contract, but the original server's exact label is unrecovered.

## Save migration and checks

### Aging, resource replenishment and item-shop repairs in 0.3.17

The native job countdown is `last_update + update_interval`. Applying the
10-second gathering refresh to babies/parents restarted that countdown on every
poll. Nursing now uses the child's fixed birthday deadline, and childhood uses
the adulthood deadline. Birthdays and individual deathdays remain saved;
offline advancement can cross both growth boundaries and releases the nursing
parent. Dead villagers are excluded from the displayed food-consumption rate.
The existing local configuration remains one real hour per age unit: baby to
child at age 2, adult at 10, elder at 65, with each villager's saved deathday
controlling death. These are local defaults, not recovered original server
lifespans. The bundled baby/parent job maximum is four hours; that upper bound
does not establish the original server's chosen duration.

The original temple display and food-poll callback use **per-minute** units.
The former backend displayed that rate but charged it per hour, a 60-fold
mismatch. Food now decreases at the displayed rate: one unit per minute for
each owned living villager at home, including babies and children. That
per-resident coefficient is a local policy; the original server's coefficient
is unknown. Guests, dead people and absent travellers are excluded. Fractional
consumption persists across polls/restarts, empty stores accrue no debt, and
updating starts the new policy at the update time without retroactive charges
at the faster rate. See [food evidence](../evidence/meego-food.md).

Work-stat progress now counts actual delivered resources instead of one point
of progress per trip. A five-unit delivery counts as five toward the local
60-unit threshold, and partial storage/stock count only the delivered amount.
Previously earned stats and partial progress remain preserved; no retroactive
yield is invented. See [work-stat evidence](../evidence/meego-work-stats.md).

Birthstones retain all 35 original metadata records and images, including
Rabbit. Login/resume now supplies a versioned original-table refresh (local
revision 2.9401) because the native client ignores equal-version patches.
Discovered collections add only stones carried by owned villagers, grouped by
their original common/uncommon/rare tiers; unseen stones stay undiscovered.
Existing prepared files and APK signatures remain unchanged. Empty saved
collections were confirmed; the reported blank Rabbit popup still requires
a native visual check. See [birthstone evidence](../evidence/meego-birthstones.md).

The original client recovers missing resources during startup toward pools of
four rocks, three trees and three berry bushes. A supplemental local check now
restores at most one missing node per 15 minutes, reusing only previously
observed unoccupied resource positions. It preserves current nodes and player
buildings and creates no backlog after a long absence. Native startup recovery
can restore nodes sooner. The original periodic respawn interval was not
recovered; the 15-minute interval is explicitly a restoration choice. See
[resource evidence](../evidence/meego-ecology.md).

All bundled catalog records remain intact: 327 items, 42 buildings, 56 jobs and
135 resource packs. Normal resource-priced tools previously failed because the
local purchase handler accepted only skull prices. Purchases now use the
original stone/wood/research/prior-tool recipes and research prerequisites.
Known incorrectly saved singleton-pair research cursors become native flat
item IDs without charging again. Equipped tools remain owned and are never
silently consumed by a crafting recipe. Native temple/research locks still
apply, so a new level-one village does not immediately display every item.

Recipe/price tests cover 49 of the 50 original shop entries. Turtle Topper has
no bundled recipe or positive price and remains explicitly unsupported.
Catalog presence does not mean all item effects or acquisition paths work:
production tool bonuses, temporary boosts, appearance potions, quests,
events, treasure and travel still have missing mechanics. See the
[catalog audit](../evidence/meego-catalog.md). Real native menu refresh and
growth animations require device testing beyond the protocol tests.

Updating this policy **does not reset the current village**. Existing earned resource balances, local currency, crystal skulls, villagers, equipped items and base stats are preserved. The one-time economy migration reduces remaining resource-node counts above the new 40/30/20 limits and replaces the previous amount-per-second job defaults with completed-trip accounting; it does not subtract those amounts from the bank. Normal ongoing play can still consume food and spend resources. The separate **New village (no bonuses)** action remains an explicit start-over operation with a backup; updating or reopening is not that action.

Newcomer deadlines, monotonic IDs, fractional trip accounting, work progress, classes and pending report cards persist in the local save. Newcomer scheduling and work/class progression bookkeeping stay outside the native game-state payload; gather timing/fractions remain in the saved job accounting fields. These helpers never reset Android, remove its packages or delete game saves.

Deterministic tests exercise completed-trip resource conservation across many updates and JSON restart, two workers exhausting one finite node, full-storage behavior, fractional yields and clock rollback. Separate tests exercise newcomer deadlines/capacity/ID collisions and stat-item/class validation and retry behavior. These tests verify local simulation and protocol behavior; they do not replace real-device checks of native animations, report-card menus, hut indicators, camera responsiveness or original balance. See [MEEGO_TEST_RESULTS.md](MEEGO_TEST_RESULTS.md) and [TOUCH_DIAGNOSTICS.md](TOUCH_DIAGNOSTICS.md) for dated observations, which must be read within their tested version and scope.

### Completed hut expiry correction (0.3.18)

The native building reader interprets an absent `expire_date` as its no-timer
sentinel, while numeric zero is an overdue Unix-epoch deadline. The HTTP layer
now omits zero expiry fields only on building records. Saved data keeps its
existing values; positive construction deadlines, job timers and resource
balances retain their contracts. Login, nested state and action responses use
the same projection. In the actual village, the completed hut's request loop
(about one request per 1.08 seconds) stopped after updating, and the user
confirmed the orange blinking stopped. This does not certify camera latency.
See `evidence/meego-hut-expiry.md` and `evidence/meego-0318-hut-live.json`.

### Camera input and render timing — 0.3.19 candidate

The exact v1.32 native library now has a reviewed move-gate patch in the
restoration plan: discarding an event no longer advances the timestamp of the
last delivered move. The existing 8.333-ms threshold, touch coordinates,
selection controls, camera bounds and rebound animation are preserved.

Normal Play reads Android's active display mode after runtime readiness. If
all reported active modes are approximately 90 Hz, it selects the reviewed
90-Hz native render timer. Otherwise it keeps the original 60-Hz timer. Supported
mode lists and the host panel rate do not count as active guest modes. The
timer choice is revisited on the next Play; a mid-game display change does not
alter the timer. No display settings or system performance controls are changed.

The prepared plan records a camera repair revision and timer rate. An older
client, or one prepared for a different rate, is rebuilt automatically on Play
using the original APK and existing local signing identity. A matching client
is reused. Missing preparation tools produce a Setup instruction; failed
preparation keeps the previous artifact reference. Android updates retain the
existing package/data through the normal `install -r` path, and the local
village save is never reset by this update.

Following authorization to try the update, the 0.3.19 launcher was built and
installed. Targeted source/packaged tests passed, and an isolated game APK was
built with matching signing identity and unchanged copied save. A forced
service-data preparation failure retained the previous artifact reference.
The normal cold-start attempt timed out at runtime authorization before
installing or launching the game. The current live village hash stayed
unchanged. The previously installed game APK and native-Wayland nested helper
were preserved. Once runtime authorization succeeds, Play can prepare the
input repair and select its timer from the active guest mode; a 60-Hz guest
still uses the original 60-Hz timer. The direct 90-Hz display experiment was
not promoted to the default.

Improved camera smoothness and under-15-ms physical latency remain unverified.
Static evidence and unresolved recovery/batching questions are in
`evidence/camera-display-comparison/pinch-code-findings.md`; trial results are
in `evidence/camera-display-comparison/camera-0319-validation.json`.


### 0.3.23 food session policy (supersedes earlier offline-food details)

Food balance now freezes across closed-game intervals. Both food use and food
trips pause; no bush/farm stock is lost. Other offline progress remains enabled.
Positive food publishes native fed/neutral mood2, empty food publishes hungry1;
the old permanent starter0 was a missing synchronization bug. Detailed local
policy, original-client evidence and test scope: [MEEGO_FOOD_POLICY.md](MEEGO_FOOD_POLICY.md).
