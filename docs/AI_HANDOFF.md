## 0.3.21 optional Mods / Skip timer (2026-10-15)

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

## Native relocation lifecycle and rotation follow-up

Supersedes the earlier position-only move fix. User confirmed green-check
acceptance still left the building transparent. Logs proved first move675 ->
2765 was saved to building16; a second request still used675. Updating location
on the existing model did not complete the client's relocation lifecycle.

Offline native analysis: JFBuilding.getTileIndex at0x7e7cbc returns the model's
building_id; JFBuildingStateMovePlacement.placeBuildingWithCallback at0x8c1cac
looks up map objects using source/destination tile indices. Register observers
at0x7e89fc track progress/state/type, not location. New relocation helper rekeys
only a moved building to its destination tile identity, emits a persistent
explicit old-model deletion and creates the destination model. Handler replies
combine resource and relocation tombstones (bounded512 each, live reused IDs
still excluded). No bulk ID/save migration. Normal Play/reopen uses existing
saved positions; only a user move invokes this lifecycle.

Worker source/target/depot references, building destinations and school session/
report keys follow the new identity. Building content, progress, paid deadline,
production-cycle and item inventory remain intact. local_instance_id preserves
commercial deterministic rolls and progression event/replay identity through
repeated moves. Identity collisions reject before changing the transaction.

Rotation: original native facing values are1 and2, and legacy local0 remains
accepted. The previous high=1 validation rejected native2. Updated purchase,
resource placement, move and ecology-site validation together; unknown3 remains
rejected. Native initialization at0x7e28c0/0x7e2904 explicitly handles2/1.

Tests include two successive moves with model-cache deletion/addition,
actual Handler.reply JSON, collision/overlap rejection, orientation2 placement
and moves, same-position facing change, preserved active work/school/items/
deadlines, stable reward roll and progression replay denial. Source31 original
rule checks passed. An in-memory copy of the live island produced old16=null
and new2391 with matching destination identity/facing2; real save unchanged.
Candidate: dist/APK-Revival-0.3.20-relocation-candidate.
Executable SHA256:
9d811f7ff4ce7e609fa25aec5c20be604d96eae5df5db339da343fcb9fc978c5.
All328 packaged tests passed, including the added simulation suite. Its
restart/pairing check now freezes the request clock to prevent a real second
elapsing from falsely flagging a one-second infant countdown difference.
Installed with all17 protected files hash-identical; the installed version/
certificate probe passed. Native green-check move/rotation remains pending
user confirmation after reopening.

User also asked feasibility of an optional in-game Skip button. This is feasible
but NOT implemented in this movement hotfix. It must target one selected timer,
remain opt-in and avoid global clock changes/aging/food side effects. Existing
finish/speed-up actions provide backend starting points; the new in-game menu
button needs separate native client/layout work and cannot be claimed from a
launcher setting or a free premium-action backend alone.

---

## Requested five-minute resource supply

Ecology policy is now local-resource-replenishment-per-kind-5m-v3. At most one
missing rock40, tree30 and food bush75 appears together per300-second check,
using the same observed safe sites, with the requested cap of6 of each type. This is user-requested
local balance; original server timing is still unverified. Standing stock,
bank balances, saves and APKs are not refilled/reset.

Both old15-minute policies migrate their next_due by subtracting600 seconds,
retaining the cycle start rather than restarting a fresh timer on every poll.
Once overdue, a single bounded per-kind check runs; no accumulated offline
backlog. Tests check299s has no spawn,300s replenishes all three, next due600s,
no deadline postponement by polling, both legacy migrations, occupied sites,
the shared6-per-kind ceiling and unchanged bank/villagers. Eleven ecology tests passed. The native place_resource route uses the same
central cap, so startup placement cannot bypass it. Existing stock is never
deleted to enforce the ceiling; saturated types skip new placement. More
than the native original3/3/4 sites can be used only when previously observed
additional safe sites exist. Never guess new terrain coordinates.
Candidate: dist/APK-Revival-0.3.20-five-minute-six-candidate.
All307 packaged tests passed. Executable SHA256:
740cf94ce94fc37101e783a1abb9ba4957a26701a583bb95ca6eaee20a6e4260.
Full test/install evidence is recorded in build/five-minute-six-*.log and
installed-five-minute-six-update.json. Installed with all17 protected save/profile/APK files hash-identical and
installed version/certificate probe passing. Native five-minute respawn observation
remains pending normal play; no physical wall-clock test is claimed.

---

## Building moves and Turtle Topper follow-up

Confirmed native requests move_building building_id=675 -> to_position2693
failed while the real building ID was16 at location675. Native
JMVillageClient moveBuilding:from:to:withCallback:andOrientation: at0xa35990
sends FROM POSITION as building_id. The local handler now resolves the exact
current position for moves, with existing ID fallback when no position matches.
Upgrade/delete retain their real ID contract. Two successive position-based
moves, overlap rejection, preserved identity/bank and JSON restart are tested.
The exact failed request succeeded on a read-only copy of the user's island;
no live move or save rewrite was performed.

Turtle Topper had activated successfully: logs showed cooldown rejection on a
second press and saved gather_rate3.06. Native JMVillagerItem.cooldown is an
NSDate (getter0x8dcf68; isOnCooldown0x8dce2c compares with now), while the server
emitted remaining seconds. Wire-only projection now sends a decimal absolute
expiry (last_update+remaining); the stored save format is unchanged. The
native JMEffect record for visible buff indicators was also absent. Production
receipts now publish the original item ID/expiry into the appropriate village
or villager effects list. Existing active receipts gain the icon on refresh;
owned expired icons alone are removed. Backend work multipliers still read
only the existing receipts, avoiding double application. Original Topper is
1.5x for180s and reusable after720s under documented local cooldown policy.

Rabbit card remains under investigation, NOT claimed fixed. All35 original
records and images exist, including Rabbit4. User clarified the blank card is
on a villager screen, not the Temple collection. Current saved traits are
Lizard1 for the three adults and Turtle3 for Lowsee, one per villager; none has
Rabbit. Native setBirthstoneDisplay always draws two slots; a nil second stone
leaves default UI artwork, and a click may initialize a nil detail popup.
The user was asked which villager/left-or-right icon to distinguish that case
from an actual catalog lookup failure. Do not invent a second trait, grant
Rabbit, reset the island or claim metadata completeness proves native UI works.

Candidate: dist/APK-Revival-0.3.20-move-topper-final-candidate.
Executable SHA256:
6896c30ac19edf2a49ec61db034d8a756d697ae8339a32192bc2ad71cfaa28a9.
Source core original-rule regressions26 passed; all305 frozen packaged tests
passed. Frozen full-suite results and
installation receipt are in build/move-topper-*.log and installed-move-topper-update.json.
Candidate is installed; all17 protected files were hash-identical across the
replacement and the installed version/certificate probe passed. Native
move/Topper screen confirmation remains pending normal Play.

---

## Respawn, runtime permission and cold-display follow-up

Supersedes the earlier pending password/startup notes below. User completed the
corrected Setup installer at20:36, which verifies actual uncached sudo access
as their non-root account. The next Play reached a running game; the initial
black window was startup, then the game opened. Reboot remains untested.

The old sudoers rule sorted before SteamOS general rules. Syntax passed while
noninteractive Play failed with `sudo: a password is required`. The installer
now migrates only its own rule to zzzzzzzzzz-apk-revival-runtime and, after
visudo, runs the fixed helper's probe through runuser -> sudo -k -n. Failed
verification rolls back dedicated files. Corrected installer was installed
separately in the existing application so the user could recover immediately.
No unrelated sudo policy or game data was modified.

That cold launch exposed another defect: the .desktop entry does not inherit
APKR_RUNTIME_DISPLAY=desktop from the prior development launch, so Cage opened
instead of the previously tested direct KDE game window. The transient
fullscreen request succeeded but matched no host game window inside Cage.
RuntimeManager now defaults to the explicitly supplied KDE Wayland socket;
the shell still validates ownership. Explicit nested overrides and Gaming Mode
remain untouched. Stop now releases the launcher's owned Android session after
stopping the app/backend; externally shared sessions remain protected.

Resource scarcity: old ecology spawned ONE TOTAL node every15min, so a resource
kind could wait45min. It now spawns up to one missing node OF EACH KIND per15min:
rock40, tree30, food bush75. Existing node contents and bank balances are never
refilled, original pool ceilings remain, occupied/unknown sites are skipped,
valid previously observed positions are reused, and old deadlines survive
migration. No unlimited offline backlog. These times are local balance policy,
not verified original server timing. Native startup also restores missing
pools: the user's latest reopened save had full pools (4/3/3), which the new
scheduler correctly left alone. On a read-only copy, simulated depletion of
one each restored all three together without changing the real save or bank.

Latest candidate: dist/APK-Revival-0.3.20-respawn-stop-candidate.
This candidate is now installed. All17 protected save/profile/APK files
remained hash-identical during the atomic replacement, and the installed
version/certificate probe passed. Native fullscreen, Stop-window cleanup
and on-screen respawn confirmation remain pending the user relaunch. New focused ecology checks10 passed;
original-APK-rule replenishment integration passed. Packaging succeeded.
All269 packaged checks passed. Executable SHA256:
a8c9a3016ccc5068e40e5cff2a5227acdb0f0c89fbc813cd53e9db3107b6ebdb.

---

## Fullscreen follow-up — October 15

User confirmed Lowsee has a normal countdown and has become a child. This is
physical confirmation of the previous baby timer/growth fix.

New game_window.py requests fullscreen on KDE Wayland only for the exact
Waydroid game app_id (waydroid.<package>), both existing and newly opened normal
windows. Play installs a transient KWin script before activity launch; stop
unloads that script. No permanent KDE rules, resolution, input mapping or saves
are changed. Existing Android immersive policy remains package-scoped. Phone
ADB devices and Gaming Mode do not receive KDE requests. Host D-Bus is blocked
inside the development sandbox; actual fullscreen must be confirmed via normal
Play outside the sandbox. The UI title bar and KDE panel in the user's photo
were desktop presentation, which Android immersive settings cannot remove.

The updated package remains version 0.3.20 (fullscreen hotfix). Candidate:
dist/APK-Revival-0.3.20-fullscreen-candidate. Executable SHA256:
a74636b55010fb83dc9b0ef86ec8f88acda09d0f96b053caaf7471ac866ccf51.
253 packaged tests passed, including all five new fullscreen checks.
Prior harvest archive below predates fullscreen. Initial JS test required
QtQml absent from the minimal bundle; the corrected test executes real JS using
the Deck's existing Duktape library. Runtime preflight ordering test now isolates
privilege routing instead of assuming the optional helper is absent.

Offline timers already use saved timestamps and catch up on reopen; no network
or always-running Deck is needed. Work/food catch-up is capped at 24 hours;
birthdays remain absolute dates (2h baby, 10h adult under current local policy).
Construction, production and solo-adventure stages still require their normal
assignments/resources/claims. This is local restoration policy, not recovered
proof of original server balance.

The password-free runtime helper and sudoers file now exist on the host;
actual unattended cold-start/reboot success is still unverified here. Do not
interpret sandbox sudo failure as proof the host helper failed.

---

# Deck integration handoff — 0.3.20

Use `deck-0.3.20-launcher-meego` for the complete merged launcher, gameplay,
build scripts, tests and documentation. `deck-0.3.19-meego` retains the game
patch export; its latest gameplay fix commit is
`df0ff6eec648e1c122a793b0d4e7eaeea491dad7`. No GitHub main merge or public
release has been performed.

The upstream launcher release is v0.3.8, commit
`775d190baf4477e3e1491435b1e0f77fb1add98d`. Its design was merged with the
working Deck branch, retaining diagnostics, recovery, original APK importing,
three restoration paths and existing gameplay/camera controls.

## Latest fixes

- The596523:14:07 infant timer is INT_MAX seconds. The native NSDate binder
  requires decimal JSON numbers. Aging stored integral last_update values;
  wire projection now emits decimals without altering birthdays/deadlines.
- Exhausted trees, bushes and rocks send explicit null deletion markers to
  the native merging model. Server-side final pickup was already conserved.
  Markers are bounded, restart-safe, skip live reused IDs and exclude dungeons.
- Requested base carrying capacity is2 for stone/wood/food. Existing skill,
  tool/boost bonuses, stock conservation and60 delivered-unit stat threshold
  remain. Research retains base1. This is documented local balance.
- Portable export packaging includes the project .py files it needs instead
  of assuming synthetic PYZ module paths are real source directories.
- Long title/package labels no longer stretch/clamp the details controls.

## What actually ran

121 original-rule Meego source regressions passed;100 related checks passed
(52 aging/trip/simulation/skill plus48 effect/production/wire/ecology);
248 packaged launcher/gameplay tests passed
without source overrides. The earlier merged build also passed offscreen Qt
preview at1280x800 and1000x650 and actual archive staging/probe checks.
The final gameplay hotfix rebuilt successfully, passed its packaged suite, and
passed actual archive extraction/staging plus the child version/certificate probe.
Physical timer/resource cleanup confirmation after reopening is still pending.

On this Deck, full launcher0.3.20 is installed at
`~/.local/share/apk-revival-app`. All17 protected save/profile/APK files were
hash-identical before/after replacement. The existing live island was NOT reset.
The earlier requested fresh start has since gained a baby: preserve that save.
Installed executable SHA256:
`d7a11c893a6104512cdd968799b940d2d3b6c86b15564d366dd93dccc8da4573`.

Local integration checkout:
`/home/deck/Apk-revival-merged-0.3.19-v0.3.8`, branch
`merge/launcher-0.3.8-meego`. Current candidate is
`dist/APK-Revival-0.3.20-harvest-candidate`; current installable tar is
`dist/APK-Revival-0.3.20-linux-x86_64.tar.gz`, SHA256
`3b3741d376629043bd5f722bf375dcba9baf0d0f9d99c43def3abec4d9d76b37`.
Old candidates/archives remain but lack the final fixes. Build receipts and
test logs are local under build/, and are not private-data uploads.

## Password-free startup: prepared, not yet host-verified

Setup -> Enable password-free startup requests one final administrator
authorization to install a root-owned helper with exactly five fixed main
runtime actions. No password-free shell or user-controlled script is granted.
See RUNTIME_ACCESS.md. The sandbox cannot elevate (no-new-privileges), so this
system configuration has NOT been installed by the agent. The user must use
the host Setup action, then test cold startup, a second launch and reboot.
Do not claim that repeated password prompts are gone until that check passes.

Waydroid remains the actual Android runtime; APK Revival manages it. No Android
reset, security disabling, system firmware/partition change or save deletion.
All APKs, user saves, signing keys and private raw native evidence are excluded
from GitHub. Original binary analysis used private files and offline LLVM/ELF;
the tests reference a user-supplied APK via APKR_MEEGO_APK.

Next: verify finite infant countdown (a new baby is the clearest check), final
node disappearance, two-unit pickups, and password-free host startup. Preserve
the current island. See OVERNIGHT_HANDOFF.md for full chronological evidence.
