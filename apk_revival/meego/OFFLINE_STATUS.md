# Meego offline restoration status — 0.3.19 source

This is a partial reconstruction of the unavailable game service, not a claim
of complete original-server parity. Original APK assets are supplied privately
by the player; this source tree contains neither that APK nor a personal save.
Waydroid remains the Android runtime dependency. APK Revival manages it behind
Play; it does not replace Android with a new runtime.

## Latest source changes, not installed on the Deck

- Wild bushes start with 75 food. One additive migration gives old standing
  bushes their extra 55 remaining food once, preserving already harvested food
  and bank balances. Rocks stay at 40 and trees at 30.
- The native response projects a finite source's last pickup no larger than its
  remaining stock. Saved rates/fractions are unchanged. Simulation tests prove
  one-unit depletion and credit without overpayment for all three wild kinds;
  the native cause of the reported stuck pickup is not conclusively recovered,
  so the client-side improvement still needs a device trial.
- Original Farm/Quarry/Sawmill stocking jobs can activate idle buildings, use
  original timings/unlocks/costs and produce finite stocks. Actual depletion
  returns the building to idle. Assignments require a genuine receiving depot.
- Owned equipped tools affect matching job yields/timing. Supported temporary
  self/village boosts expire across offline catch-up. Equipment/boost changes
  update active job values in the same response, without a duplicate global
  native boost. Supported hair/age/Mojo items and child-play ball scripts have
  explicit, validated item paths. Unsupported effects reject without consumption.
- Future births and permanent arrivals get valid original appearance slots and
  birthstones, with locally documented stat/inheritance rules. Existing people
  are not rewritten. Collection discoveries and supported earned achievements
  are synchronized without inventing currency payouts.
- Existing prepared clients load additional original progression rules read-only
  from their selected APK; the prepared data files are not rewritten.

## Verification on 2026-10-15

118 focused automated tests passed using original bundled rules, fixed clocks
and temporary/synthetic villages. Coverage includes jobs, aging, food, ecology,
skills, wire responses, production, population, item effects, progression,
final-unit collection and poll/restart invariance for effect expiry. No live
gameplay, Android install or personal save mutation was performed for these
latest changes. Earlier user feedback that the camera worked well applies to
the previously installed camera repair, not to new gameplay validation.

The full default discovery attempt ran 377 tests with one release-note assertion
failure, nine errors and ten skips. The release-note assertion was repaired
locally; eight errors required sockets denied by the sandbox, and one required
the unavailable PySide6 dependency. See the local development handoff for the
subsequent supported-suite results:371 tests ran,362 passed and9 skipped,
excluding socket-dependent backend/real-Meego integration and the missing-Qt
UI module. The118 focused tests are part of this count. No release candidate
is certified by this.

## Explicit reconstruction policies

Original tables provide content, costs, limits and many durations, but not all
former server formulas. The following are local policies: stock initialization
from industrial stocked-state default_length; base stat-to-yield coefficients;
additive/multiplicative effect composition; reusable-item cooldown origin;
once-per-activation child-play stat benefits; newborn genetics/newcomer stats;
unseen-first birthstone generation; 15-minute resource replenishment at known
unoccupied sites; permanent-arrival scheduling; age/food configuration; and
elapsed-time achievement accounting. They must not be described as recovered
original-server behavior. Original food-rate consumption is not reduced to
hide a village producing less food than it consumes.

## Remaining core gaps

- Commercial operator cycles use original costs and one-hour timing, but their
  earned random-drop/collection reward path is not implemented. They currently
  expire without item payout: do not spend food on these expecting rewards.
- Solo treasure mini-game reward sessions, Launch Dock/Quest Portal travel,
  solo quests/dungeons and special dungeon jobs remain unsupported/deferred.
  Bundled maps and assets alone do not make those mechanics functional.
- Some scripted minigame/infection/quest-booster items remain rejected. Local
  Photo Hut capture and some native catalog/menu paths still need verification.
- Original achievement/tutorial payout amounts and several balance/genetics
  formulas remain unknown. No invented skull reward is claimed as original.
- Tourists identified by the original client are other players' visitors;
  social travel, tribes, gifting, online events and payments are deliberately
  excluded. Permanent local arrivals are a separate implemented feature.
- Runtime reboot recovery, direct-display preference persistence and physical
  latency below 15 ms are not newly verified. No fresh input/runtime measurement
  was taken during this source-only change.

The requested GitHub export copies only apk_revival/ and resources/ onto
df989d1. Root packaging metadata, tests and documentation intentionally remain
at that base in the export. In particular pyproject.toml still says 0.3.7 while
the exported Python package says 0.3.19. A merge must reconcile packaging version,
release notes and regression tests before packaging; this is a review branch,
not an installable or publicly published release.
