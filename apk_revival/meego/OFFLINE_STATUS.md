# Meego offline restoration — 0.3.19 review branch

This is a playable local reconstruction candidate, not recovered server code or
verified complete original-server parity. It requires the player's original APK
and the existing Waydroid runtime. No proprietary APK, save or signing key is
included in this branch. The existing launcher design is preserved.

## Implemented source workflow

- Existing farm/quarry/sawmill activation, stocking, finite harvesting and depot
  validation; owned tools and temporary boosts affect actual work. Wild bushes
  hold75 food, and final-unit pickups are clipped on the wire without changing
  saved rates or overcrediting rocks/trees/bushes.
- All seven commercial building families stage earned original catalog items
  after paid, fully worked cycles. Explicit collection credits village inventory
  once. Original job-attempt tiers unlock the bundled reward pools.
- Native bird/egg treasure sessions use recovered HMAC-SHA256 request validation,
  persistent opportunity/expiry clocks and replay-safe claims. Local policy:
  one skull per earned session, at most one opportunity/hour, no upfront payout
  or offline backlog. Native JSON whitespace compatibility still needs a Deck
  check; invalid signatures fail closed.
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
