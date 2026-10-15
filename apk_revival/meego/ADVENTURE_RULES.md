# Offline solo adventures: implementation and limits

This source implements a local solo adaptation of **Ice Bear Cave (type 2)**
and **Turtle's Grotto (type 3)** from the user's original Meego 1.32 rules.
It does not restore other players, tribes, chat, visits or a remote service.
The inactive older Turtle definition (type 1) is not enabled.

## Recovered contracts

Original APK SHA-256:
`030613cbc63bd03786545999c3590456a264796866127898928a4d59988d29a2`.
Original native library SHA-256:
`6b1000dccb517635a51656dd0439f49052a361b9a2a905b3e21453c481b3dcf3`.

Static Objective-C metadata establishes these model fields:

- `JMDungeonPacket`: `user_dungeon` (`JMUserDungeonView`) and
  `dungeon_game_state` (`JMGameState`); its underlying `game_state` dictionary
  updates the island. Native metadata location `0xc165f0`.
- `JMUserDungeonView`: `dungeon_id`, `dungeon_type_id`, `stage_level`,
  `user_id`, `username`, `user_avatar_id`, `slots_filled`,
  `dungeon_expire_date`, `stars`. Metadata `0xc1caa4`.
- `JMDungeonQuest`: `dungeon_id`, `start_date`, `end_date`,
  `from_username`, `time_worked`, `gold_count`, `job_activations`,
  `chat_blocked`. Metadata `0xc17144`.
- `JMDungeonResultsPacket`: `game_state`, `dungeon_results`,
  `user_dungeon`, `dungeon_summary`; summaries contain typed villager
  identities, appearance IDs, work/gold counters and `quest_results`.
  Metadata `0xc17374` / `0xc1734c`. `dungeon_results` maps a numeric
  result identity to **JMQuestResult**, a different model from the summary
  entries: `resource_rewards`, `bonus_resource_rewards`, `item_rewards`,
  `points_reward`, `additional_bonus_rewards`. The reward menu copies this
  dictionary (`0x81e538`), selects a numeric key (`0x81e5f4`), then binds
  the value as `JMQuestResult` (`0x81e658` / `0x81e674`; class `0xc17554`).
- `JMDungeonQuestResult`: `resources`, `bonus_resources`, `items`,
  `points`, `additional_bonus_rewards_key`. Metadata `0xc17324`. Its
  `items` is item-ID-to-numeric-count, not an inventory record dictionary:
  native summary conversion reads the first `allKeys` value's `intValue`
  (`0x81fdb4`) and first `allValues` value's `intValue` (`0x81fe58`), then
  sets the displayed item ID/count. At most one item kind is displayed per
  participant result; multiple reward kinds would be misleading in that UI.
- `JMVillager.isDungeoneering` compares `location_type == 1`
  (`0xa51d14`); the island retains the villager but marks it away.

Original request methods and route strings were recovered at:
`start_dungeon` (`0xa3cfd0`), `get_active_dungeon` (`0xa3d410`),
`get_dungeon` (`0xa3d61c`), `send_villager_to_dungeon` (`0xa3d798`),
`complete_dungeon_quest` (`0xa3de2c`), `get_dungeons_list` (`0xa3dfd8`),
`update_building` (`0x6f9184`), `set_job` (`0x6f942c`),
`update_villager_job` (`0x6f95d8`), `update_dungeon` (`0x6f98cc`).
The last method sends `dungeon_id` and `current_stage_level`.
The complete-quest method sends `villager_id`.

These are **static packet contracts**, not evidence that an installed native
client has successfully played through the new implementation.

## Original data reused

The engine reads the original `dungeon_types` and `dungeon_stages` tables at
runtime. Stages retain their exact building types, encoded positions,
orientation, initial state, parent/child activation links, original idle
roles and durations. It does not ship copied game art or a replacement map.
A completed Quest Portal is required, and the original 1/2 skull entry costs
are charged once per session. Existing island resources and villagers remain
in place; no world reset or starter grant is performed.

Supported original adventure jobs are 51–62, including pumps, furnaces,
space heaters, regular/super chippers, drillers and fishers. Original source
restrictions, cycle durations, guaranteed `random_drop/0/373` constants,
finite fishing-hole counts, role transitions and activation costs are used.
There is no random invented inventory reward. Resource item 373 maps to
resource 5 (gold) under the existing island resource mapping.

The heater activates its original linked stalagmites only while operating.
Settlement splits on its completion, so children stop at that instant even
if the next poll arrives minutes later. Fishing stock is consumed once;
repeated polls and retried assignments do not refill it. Work is earned only
while assigned. Completing one finite activation does not silently repeat it
for the entire time the application was closed.

## Explicit local adaptation policies

The original remote service's complete adventure balancing is unavailable.
These choices are therefore labelled local, not claimed original behavior:

- One active solo session per save. Multiple **owned** adult villagers may
  join, bounded by the original type's participant-slot limit; no fictitious
  other players are created. Nursing parents and unavailable villagers cannot
  depart. Working villagers must have an interruptible original job.
- Original stage durations advance the local stage clock. A single player
  is not blocked behind a progress threshold originally designed for several
  players. Original `time_worked` breakpoints still determine the reported
  star index; no unearned work is added to reach them.
- Original stocked-phase `default_length` is interpreted as the finite
  number of fish trips (4 or 5). Original gathering time is used per trip.
- Earned guaranteed job gold is accumulated in the session and paid to the
  island only on an accepted results claim after the original total session
  deadline. Idle time, client-supplied balances and early completion requests
  earn nothing. A completed session with no work returns villagers with no
  reward; it does not trap them away forever.
- Owned Turtle Soup/Walrus Musk original coefficients 20/50 are interpreted
  as a percentage of gold earned by completed cycles while the boost is
  active. The effect system chooses the maximum active owned coefficient.
  Fractional percent units persist and round down once on collection; a
  bonus earned before expiry survives a later claim. This is not a recovered
  original server reward formula.
- Original server item odds are unavailable. New-policy sessions use an
  explicitly LOCAL earned-item table in `engine/adventure_loot.py`: one original
  themed item after at least 60 seconds of actual assigned work, one activation
  and positive earned gold. Turtle items are1185–1188/1505–1509; ice items are
  1510–1515. Membership follows original imagery/descriptions; the displayed
  local weights are not original rarity. One deterministic roll per participant
  survives restart/retry, honors owned caps and never grants a premium skull
  refund. Older pre-policy sessions do not gain retroactive loot. Native result
  and summary item count maps match the inventory credit atomically.

Claims are per participant and persistent across JSON/save restart. Retrying
an accepted claim returns its immutable reward breakdown with the **current**
island snapshot and never pays twice. Explicit requests for an older session
cannot claim, close or alter a newer session. Recent completed sessions are
bounded to 31 archives; monotonically increasing IDs are never reused, and
older requests fail rather than recreating a payable session.

## Integration and validation

`adventures.handle(data, route, params, rules, now)` returns
`(new_save, native_response)`, or `None` for an unrelated route. It copies the
input before any validation/mutation. The existing server must hold its save
lock, atomically persist `new_save`, then send the returned response.

`adventures.advance(data, now, rules)` settles a copied save in place. Invoke
it within the existing effect-boundary simulation segments **before** expired
item-effect receipts are removed. `is_away(data, person_id)` is a read-only
helper; island job, breeding and inventory mutations must reject participants
whose `location_type` is 1.

`apk_revival/meego/regression_tests/test_meego_adventures.py` passes **40 tests**: 20 with small authored
fixtures and 20 against the read-only original APK. They cover typed packet
fields, stage reconstruction, start/claim retry, early and forged completion,
JSON restart, no-work offline intervals, heater/chipper polling invariance,
finite fishing, drilling, paid activation, nursing protection, participant
capacity, per-participant payouts and effect expiry. These are automated
backend tests on synthetic saves, not real-device/native UI tests.

Remaining verification: original native adventure entry/return, map camera,
stage-transition animations, completion/result screens, scene-specific UI
field expectations, and end-to-end save continuity on a test installation.
No installed application, APK, personal configuration or live save was
modified during this source implementation. Launch Dock is original travel
to **other villages**, which remains excluded. A separate generic solo quest
catalogue has not been recovered and is not fabricated by this module.
