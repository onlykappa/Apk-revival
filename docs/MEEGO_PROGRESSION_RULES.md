# Offline progression: recovered rules and limits

The progression engine reads the original APK's `TechTree.plist`. This is a
partial offline reconstruction, not a claim of original-server parity.

## Implemented

- Successful, validated births increment achievement 105 using the original
  thresholds: 2, 40, 150, 500 and 1,000. Completed breeding tokens are recorded
  persistently before the shorter request-retry cache expires. Replaying a
  request does not create another objective completion.
- Discovered, known birthstones unlock achievements 160, 173 and 174 at the
  bundled collection thresholds. Duplicates and unknown IDs do not contribute.
  Existing discoveries and earned achievement levels remain intact.
- Accepted production starts unlock Farm/Quarry/Sawmill achievements 128, 131
  and 130 at the original 9/18-use thresholds. Repeated polls do not contribute.
  Uses are tracked per building instance; this counter scope is a local policy
  because the original server's aggregation behavior has not been recovered.
- Tutorial acknowledgements accept original task names or numeric task IDs.
  Completed buildings also acknowledge their bundled `completes_tutorial_tasks`
  entries. Already acknowledged tasks are preserved and not awarded again.
- Time achievements use the original displayed day/year thresholds. Counting
  elapsed village age, including time offline, is an explicit local policy;
  the original definition of "Time Played" has not been recovered. Years use
  365 days. This never grants an invented XP balance.
- The affluence meter uses fixed milestones from the original completed temple
  affluence values, replacing the moving `affluence + 100` placeholder. This is
  a local UI policy, **not** a recovered original island level formula. The
  last interval continues beyond the final milestone to keep the meter valid.
  Temple upgrades still control temple level and original purchase unlocks.

Only the achievement record changes upon earning a tier. Existing extra
achievement/save fields, inventories, resources and currency are preserved.

## Rewards and omitted systems

The original 23 achievement records and tutorial records contain no skull,
resource or item payout amount. The implementation therefore does **not**
invent payouts, award arbitrary skulls, or treat acknowledgement as a reward.
Original achievement reward parity remains unverified until an authoritative
rule source is recovered.

Social travel/tourists, tribes, gifting, popularity, moderator badges and old
online events are excluded from the user's offline core target. Their existing
earned records are preserved rather than deleted or simulated.

All 23 bundled achievement records have been classified. The 10 offline-core
IDs are 102 (temple), 105 (births), 107/338 (time), 128/130/131 (production
unlocks), and 160/173/174 (birthstone collections). Temple 102 remains owned by
the existing temple synchronization. The other 13 are deliberately excluded:
103/104/108/161/162 (social/tribe objectives), 144/206/339 (staff/community
awards), and 287/299/300/301/302 (old events). This classification covers the
bundled achievement list, not every feature in the game.

Bundled quest/dungeon stage layouts, durations, equipment modifiers and some
commercial-building drop tables exist. The original solo quest initiation,
completion/rating and authoritative payout contracts have not been recovered
by this progression work. They remain a separate known gameplay gap; the
presence of assets does not establish a working offline quest implementation.

The original dungeon table has three definitions and four stage records:
active Ice Bear Cave (915 seconds, two stages, eight participant slots) and
active Turtle's Grotto (330 seconds, one stage, four slots), plus an inactive
older Turtle definition. Progress breakpoints, admission costs, map assets and
native session classes are present, but no authoritative payout table was
found there. Commercial buildings' `quest_rewards` entries belong to their
own item drops and must not be repurposed as dungeon rewards.

The treasure mini-game is also still deferred by the local server. The APK's
11 mini-game variants provide game/idle/reward durations and speed levels;
they do not provide an authoritative reward amount or complete server session
contract. Restoring that contract remains separate work, even with all of its
art and native client code preserved.

Births already evicted from the old 64-entry completed-birth retry cache before
this migration cannot be reconstructed reliably. Known births seed the new
persistent history; existing higher achievement levels are never lowered.

## Integration contract

Load the original `achievements` and `client_data` sections alongside existing
local rules. After calculating building affluence, call
`progression.synchronize(data, now, rules)` before atomic save persistence.

On successful child creation call `record_birth(data, completed_token)` before
the old retry-cache eviction. On an accepted production start call
`record_production_cycle(data, kind, building_id, stable_cycle_id, now, rules)`
after validating/debiting its cost. A cycle ID must be persisted and reused on
retries. Do not call this hook for polls or rejected transitions.

`complete_tutorial_task(data, task, rules)` replaces arbitrary tutorial task
acceptance; its `ValueError` should map to the normal `ActionError` response.

Validation: 12 focused automated tests passed, including two tests that read
the user's original APK privately without changing it. These cover all three
original production unlock paths, collection/birth thresholds, restart/retry
bookkeeping, unchanged balances, tutorial validation and legacy preservation.
No runtime launch, APK install or live village mutation was used for this work.
