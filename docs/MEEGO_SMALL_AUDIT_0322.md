# Focused Meego audit — 2026-10-16 / 0.3.22

Scope: reported skip visibility/freeze, adjacent timer/data handling, existing
runtime preservation and Launch Dock feasibility. This is a bounded source/log/
artifact audit, not a claim that every original feature or screen was tested.

## Confirmed and repaired

| Finding | Evidence and change |
| --- | --- |
| New baby missing from already-open picker | Healthy Nooni existed as infant job1 with nursing parent Lowsee job3, ~7100s remaining. Read-only evaluation of the actual save returned Nooni. UI loaded choices only on open/manual Refresh. Add auto-refresh, explicit selection, and clear a vanished choice instead of selecting a different task. |
| Launcher refresh can block UI | mod_state used Store.load with default integrity hashing, synchronously re-reading original APK input(s) on each refresh. Read only profile metadata for this already validated active game; Play retains original/prepared hash checks. State snapshot lock wait is bounded to50ms. |
| Picker-only workflow inconvenient | Add Skip timer beside X in native shared countdown panel, reusing original completion button/observer and input guards. Baby, child and construction callbacks finish selected work through persistent mod logic, without cost or global elapsed simulation. |
| Native panel needed a scoped preparation operation | First isolated signed build correctly rejected the initial proposed variable-length binary patch. Add a dedicated exact-asset/hash/revision operation; do not relax existing bounded same-length binary patch rules. Signed build then passed. |
| Package version drift | Align pyproject and Python package at0.3.22. |

The reported visual freeze was not fully root-caused. Game backend requests
continued and no unsupported/rejected actions appeared in the sampled session
since mod installation. That rules out a complete service outage during those
logged polls; it does not prove focus, graphics or compositor behavior. User
later confirmed picker worked after returning, then confirmed the new in-game
Skip timer worked. No runtime performance tweaks or Android reset were applied.

## Launch Dock / ten local bot islands

Feasible as an **offline local extension**, not recovered original-server parity.
A cloud AI model or live accounts are unnecessary for ten deterministic NPC
islands. Current implementation returns [] for get_neighbour_list and does not
implement send_villager or get_remote_village. Quest Portal solo adventures are
separate and already implemented; they do not make Launch Dock travel work.

Original user-owned library, offline metadata/instruction inspection:

- JMVillageClient.sendVillager:toUser:withDuration:withResourceBonus:withCallback:
  at0xa38efc sends game/village/send_villager with villager_id, to_user_id,
  duration and give_resource_bonus; it binds a local-state completion callback.
- getNeighbourList: at0xa39774 requests game/village/get_neighbour_list with size.
- getVillage: and getRemoteVillage: at0xa3ad6c/0xa3ae74 use village_id, with
  get_village and get_remote_village routes respectively.
- Existing get_village ignores village_id and returns the home snapshot. Before
  enabling any bot navigation this must distinguish identities and isolate
  remote state; reusing this fallback would display the wrong island.

Next implementation should recover the native neighbour/remote response models,
then introduce ten labeled NPC records and isolated known-valid island layouts.
Persist an outbound trip per traveller, its destination, deadline and one-time
reward receipt. Reserve home beds; preserve equipment/skills; return villagers
safely after offline time or interruption. Visiting remote views must never
replace/edit the home village. Set explicit documented local reward/cooldown/
charisma policies, cap claims, and test duplicate requests/restarts before native
rollout. Do not simply return ten names and claim visits/rewards are working.

## Other known gaps / limits

- Secondary birth-card blank/Rabbit placeholder remains unconfirmed; no trait
  was invented or granted. All35 recovered birthstone records/art assets exist.
- Legacy mailbox-only type2/3 gifts, social cloud infection flows and Photo Hut
  capture remain unsupported or unverified as documented in OFFLINE_STATUS.md.
- Local newcomers, work stats, offline simulation, production and school policy
  choices are documented approximations. Exact former-server odds/balancing
  cannot be certified from the retained APK alone.
- Reboot, new physical latency benchmarks and every native countdown phase were
  not tested this session. Prior accepted camera patches and display selection
  remain intact.

## Verification and installation

363 final packaged regressions PASS in27.165s. Includes original rule/asset,
real Qt controls, exact native-patch preconditions, complete panel round-trip,
UI button bounds, selected callback/retry handling and existing launcher/game
regressions. A separate isolated native APK build PASS in7.686s: signature and
alignment verified, same existing signer; exactly five planned members changed.
Build/probe PASS;0.3.22/certificates true. First signed attempt failed at the
restrictive panel operation validator and was repaired as described above.

Installed app SHA256:
a27e5eb3e24d3e614214256db2fe7cd2f6551aa8858c0596803496916672d3b3

All17 protected files byte-identical across the application install. Existing
island and APKs not reset/imported. User confirmed: "skip timer worked!!" after
normal Play upgraded the native client. Live request records independently show
one baby-to-child and two child-to-adult callbacks accepted as local-mod-skip-timer
with expected_cost0; the prepared client retains its90Hz camera configuration. No further physical acceptance is
claimed. Receipts/logs remain private in build/; source/tests/docs are committed.
