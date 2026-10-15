# Offline commercial production

This implementation covers the seven bundled operator buildings: Joose Hut
(11 / job 21), BBQ Pit (12 / 27), Seafood Shack (14 / 26), Cawfee Bar (18 / 37),
Nectar Bar (19 / 31), Macho Nacho (20 / 36), and Vegan Hut (21 / 38).

The bundled TechTree supplies activation food costs, the 3,600-second service
window, job IDs, item IDs, count contributions, chance values, and the 0/12/36
job-attempt tiers. Existing `production.py` charges the activation cost once.
The original native commercial menu reads `unlock_information.job_attempts`
for its active job; these tiers are not charisma thresholds. The seven sets of
three rewards match each building's bundled `quest_rewards` item IDs.

## Explicit local server reconstruction

The defunct server's rolling frequency and random-number algorithm are absent
from the APK. This is an offline reconstruction, not a claim of exact original
server odds or schedule:

* One reward opportunity after one fully staffed, paid service hour. No
  retrospective gifts for legacy cycles, no reward for an unworked/partially
  worked hour, no multiplication from duplicate assigned workers.
* Select the highest original job-attempt tier reached before this completion.
  One deterministic weighted draw can yield at most one original item. A sum of
  chances below 100 retains the remainder as no-drop probability. A sum above
  100 is normalized to its sum, keeping every original item possible (the
  Vegan Hut has 100/50/5). Original weights/counts are retained; the single-draw
  interpretation is local policy.
* A completed service increments that job's attempt count even on a miss.
  Random selection is tied to user/building/type/paid-cycle identity. Persistent
  cycle work and a settled marker prevent poll/restart rerolls and duplicate
  payouts. The tracked interval is bounded by the simulation's elapsed limit.
* Earned items accumulate in `building.items`; they are **not activated** and
  do not become global passive boosts. An explicit native collection request
  moves them into village inventory, where normal item-use rules apply.
* `game/village/collect_building_items` identifies the building by
  `building_type_id` and `location`. Collection returns the full game-state
  object, including the complete village `items` map. It is transactional,
  retry-safe, preserves existing inventory metadata, and rejects stale/missing
  locations without collecting a neighbour's inventory.

## Integration

Call `commercial.advance(copied_data, now, elapsed, rules)` immediately **before**
`production.advance_cycles`: the latter clears the operator job on expiry.
Never call either helper against an unsaved live object outside the existing
locked copy/commit transaction. Route collection through
`commercial.collect(data, params, rules, now)`, persist the returned copy, and
respond with `new['game_state']` directly.

The paid activation's `local_production_cycle` and `local_production_policy`
are the eligibility proof. Older/free timers remain usable but do not receive
retroactive rewards. `local_commercial` is bounded per-building accounting;
completed cycles do not create an ever-growing receipt list.

## Evidence and testing

Read-only original APK TechTree and retained native annotations:
`JMVillageClient.collectBuildingItems` at 0xa356c0;
`JFVillageService` collection callback at 0x8fa6b0 (reads full `items`, computes
inventory delta, binds game state); commercial attempt lookup at
0x857b74 / 0x857bdc / 0x857c1c.
No original APK, proprietary tables, saves, or private disassembly are shipped.

`apk_revival/meego/regression_tests/test_meego_commercial.py` covers paid complete/incomplete work, legacy
and unworked cycles, bounded offline gaps, same-tick retries, JSON restart,
attempt tiers, miss settlement, two paid cycles, accumulation/collection,
invalid/stale location, corrupted item validation, existing item metadata,
and all three original reward IDs for all seven buildings. These are source
simulation tests, not claims of a physical Deck UI test.
