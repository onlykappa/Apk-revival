# Meego offline restoration — 0.3.19 review branch

Latest harvest/aging follow-up: basic resources now have a requested two-unit
base; depleted trees, bushes and rocks send explicit native deletion markers;
integral last_update timestamps are projected as decimal JSON to satisfy the
native NSDate parser and prevent the596523-hour baby timer. Existing birthdays,
growth deadlines and saves remain intact. See `HARVEST_AGING_RULES.md`.

This is a playable local reconstruction candidate, not recovered server code or
verified complete original-server parity. It requires the player's original APK
and the existing Waydroid runtime. No proprietary APK, save or signing key is
included in this branch. The existing launcher design is preserved.

## Implemented source workflow

- Wild resources replenish independently: at most one rock40, tree30 and bush75
  per5-minute check, at previously observed unoccupied sites, up to the requested
  cap of6 rocks/6 trees/6 bushes, shared by native spawn requests and timers. Old15-minute deadlines are shortened from the same cycle start;
  offline backlog never adds more than one per type per check. Local timing
  is a restoration policy; original server timing remains unverified.

- Existing farm/quarry/sawmill activation, stocking, finite harvesting and depot
  validation; owned tools and temporary boosts affect actual work. Wild bushes
  hold75 food, and final-unit pickups are clipped on the wire without changing
  saved rates or overcrediting rocks/trees/bushes.
- All seven commercial building families stage earned original catalog items
  after paid, fully worked cycles. Explicit collection credits village inventory
  once. Original job-attempt tiers unlock the bundled reward pools.
- Native bird/egg treasure sessions use recovered HMAC-SHA256 request validation,
  persistent opportunity/expiry clocks and replay-safe claims. Local policy:
  one skull per distinct signed egg (0–5), at most one opportunity/hour, no
  upfront payout or offline backlog. Native signed requests were observed on
  the Deck; invalid signatures fail closed. Variant 4 is now supported too.
- Solo Turtle's Grotto and Ice Bear Cave use original maps, stage objects,
  timers, jobs, heater/chipper links, drilling/fishing stock, entry costs and
  guaranteed job gold. Participants leave island work, retain identities and
  return through restart-safe results claims. Early/spoofed/duplicate claims
  cannot generate extra rewards.
- New adventure sessions can earn one original themed item after60 seconds of
  actual work, an activation and positive job gold. All15 themed item IDs are
  reachable. Pool membership is inferred from original imagery/descriptions;
  weights and the work threshold are explicit LOCAL balance, not recovered
  server odds. Both native result formats receive the same item/count payout.
- Owned Turtle Soup/Walrus Musk activate and expire correctly; their20/50
  coefficients are interpreted locally as a percentage of earned job gold,
  using the maximum active coefficient. No after-the-fact boost is applied to
  already completed work. Original permanent-stat and age consumables remain
  supported, including earned adventure consumables.
- Existing owned cosmetic Kick Ball/Mystery Box/April Fools mailbox gifts open
  through the recovered native route and original Lua. No incoming social
  gifts are invented; the tombstone prank never changes saved deaths/stats.
- Existing births, aging, food, permanent arrivals, birthstone discovery and
  earned progression are retained. Future villagers vary using original
  eligible appearances/stones with documented local genetics policies.

## Review and verification

The new regression tests are shipped in `apk_revival/meego/regression_tests/`
so they accompany the two-folder-only GitHub export. They use authored temporary
villages and optionally read the privately owned original APK. Run:

```sh
APKR_MEEGO_APK='/path/to/original.apk' python3 -m unittest discover -s apk_revival/meego/regression_tests -v
```

95 source regression checks passed on the Deck. All95 also passed through the installed application's bundled Python3.12
against current source. These are backend,
request-parser and serialization tests, not proof of native adventure animation
or a completed physical playthrough. Private isolated review APK preparation
passed signing and alignment validation. No main app or personal save was
replaced; the review uses a different Android package and test data directory.

A real request-parser integration test covers Quest Portal waiting/departure,
assigned pump work, away-villager protection, save restart, boosted return and
replayed claims. Other checks cover paid production/collection, signed form and
nested-JSON treasure envelopes, duplicate-key rejection and token redaction.
The native result contract was corrected using actual reward-screen consumers:
`dungeon_results` maps IDs to JMQuestResult fields, while summary.quest_results
uses the different JMDungeonQuestResult fields.

## Explicit limits

- Exact former-server odds, genetics, food coefficients, progression payouts
  and reward balances are not recoverable from preserved client data alone.
  Local policies are spelled out in COMMERCIAL_RULES.md, TREASURE_RULES.md,
  ADVENTURE_RULES.md and SCRIPTED_GIFTS_RULES.md. They are not presented as an
  exact port of the unavailable server.
- Launch Dock travel and its returned social quests involve other players;
  they are excluded. The Quest Portal provides the local solo adventures.
  No fabricated remote quest catalog, visitors, chat, tribes, purchases or
  online events are enabled.
- Type2/3 reward bug gifts and social cloud infections remain unsupported and
  unconsumed. There is no verified offline acquisition/conversion route for
  legacy mailbox-only scripted gifts. Photo Hut local capture is unverified.
- Device acceptance of the new native adventure/results/script screens remains
  to be checked. No new sub15ms physical latency or reboot verification is
  claimed. Previously accepted camera behavior is retained.
- Only apk_revival/ and resources/ were exported onto df989d1 as requested.
  Root pyproject/release metadata therefore still says0.3.7 while the Python
  package says0.3.19. Reconcile metadata before a normal packaged release.
  No public release or merge is performed by this update.

## Deck review follow-up (2026-10-15)

Actual isolated native review verified five testers, Quest Portal entry,
Turtle job62 assignment, Turtle Topper purchase/equip, a successful explicit
Turtle result claim with five gold saved in its receipt, and a subsequent Ice
Bear entry with job53 assigned. Timer-poll shape, explicit-free cosmetic
purchase, distinct signed eggs, finished-stage unloading, empty offline notice
contracts and original job50 homecoming were corrected during that review.
The final packaged source repack passed 105 embedded regressions, without
redirecting imports to the working source, and the certificate/version probe.
It was applied to the main launcher with its prior executable backed up;
17 protected main save/profile/APK files matched before and after installation.
The test-only five-villager fixture was not ported into main-game defaults.

Still unverified physically: multiple egg skull payouts after the new handler,
Ice Bear's second stage and full native completion, death/resurrection screens,
and main-game Play after reopening the updated launcher. This was an offline
source repack using the existing licensed PyInstaller bootloader/dependencies,
not a clean PyInstaller rebuild or complete original-server parity certification.

### Storage / Thinking Rock follow-up

Storage's missing worker limit no longer falls back to zero housing slots:
construction accepts one builder and completes using existing timing. Thinking
Rock's native `get_research_progress` read is implemented with the recovered
three-field packet; existing work-generated research points and original-cost
explicit item research remain intact. Its progress-selection policy is local,
as described in `RESEARCH_RULES.md`; polling never grants points or unlocks.
108 focused source regressions passed before packaging. On-screen verification
of this follow-up is pending; the active user session is still Solo Review.

### Automatic discovery / fishing follow-up

The original Doctor category locks require researched item cursors. Active
Thinking Rock work now completes affordable original-cost discoveries rather
than leaving a full progress bar indefinitely. Recipe ordering is LOCAL
(cheapest eligible then numeric ID), with original temple/prerequisite gates.
No researcher means no auto-spending; discoveries unlock purchases without
granting free inventory. Native progress reads remain read-only.

Ice fishing deadlines now cover all remaining catches, and abandoning a hole
clears its countdown. Earned original job gold stays in the trip until final
claim; exhausted holes still close. Late native timer/notice reads after a
successful claim now return a closed packet instead of a repeated error.
114 focused source regressions passed; fresh native confirmation is pending.

### Leveling follow-up

Village number now agrees with its existing affluence bar instead of being
forced to the Temple level. This is the documented LOCAL milestone schedule;
the original server XP formula is not recovered. Temple achievement102,
original upgrade costs and all Temple-dependent unlocks remain independent.
Every original Temple upgrade1->14 passed a real-rule temporary-village test;
level6->7 also rejects insufficient wood and invalid level skips without debit.
See `LEVELING_RULES.md`.117 focused regressions and40 additional local related
checks passed before packaging. The user confirmed the review now displays level14.


### Equipment transfer follow-up

The native client merges equipment dictionaries with binding options27, which
leaves omitted models cached. Unequipping therefore returned inventory correctly
but left a ghost hat visible on the old wearer. Full-state wire projections now
send explicit null deletions for known inventory/equipment IDs absent from each
villager. Saves retain only actually owned equipment. This also repairs already
cached ghosts on the next state response. Original client evidence: equipment
callbacks0xa37d30/0xa3810c and strong-dictionary binding0x98a5e0; deletion of
untouched keys requires bit4, absent from27, while explicit null is deleted.

118 source regressions pass, including original Turtle Topper purchase cap,
unequip/transfer, rejected repeated removal/equip/purchase, save reload, and
non-mutating native wire projection. Physical appearance confirmation remains
pending; authoritative ownership was already conserved before this fix.
