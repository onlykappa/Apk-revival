# Meego offline-core completeness audit — 2026-10-15

## Verdict and scope

**The current adjusted APK retains the original APK's bundled game content,
but the restored offline island game is not feature-complete.** Missing
mechanics are mostly in the local simulation, rather than files lost during
APK modification. A full offline port cannot yet be certified.

The user requested a check **before further patching/installing**, then
explicitly excluded online/server-dependent features. This audit targets
fully offline island gameplay. Accounts, real-player visits, messaging,
payments and live online events are outside the completeness target. A core
mechanic originally calculated remotely still needs a working local
implementation; retaining its client data alone does not provide one.

This was read-only artifact/source/saved-state analysis. No APK was patched,
built or installed, no runtime was started/stopped, no gameplay test was run,
and no save was edited for this audit. Existing test/device evidence is
identified separately from static findings.

## What the actual APK comparison establishes

Original v1.32 APK SHA-256:
`030613cbc63bd03786545999c3590456a264796866127898928a4d59988d29a2`.

Current prepared/recently launched adjusted APK SHA-256:
`cc73b289ad0b1e360bb4f41c58bd14ca362589814f7270f45e718e3e3df6c4bd`.
Its recorded client repair is revision 1, timer 90 Hz. The latest normal
launcher activity check references this hash. No fresh ADB/device hash query
was performed during this audit; this is an on-disk APK comparison.

- Both archives contain **741 entries**, with no duplicate member names.
- **No non-signature member was removed or added.** Of the 738 non-signature
  entries, **734 are byte-identical** and four contain the intended changes.
- Changed files are the compiled package manifest, app-label resources,
  endpoint/identity `Info.plist`, and native `libverde.so`. Every change was
  reproduced exactly from the saved restoration plan. There were no
  unexplained changes.
- The native library differs in **44 bytes**, within the reviewed local
  transport, input-gate and 90-Hz timer patches. Its length is unchanged.
- `classes.dex`, all 21 Lua scripts, 326 scene files, 286 image members,
  12 compressed texture containers, and eight audio/sound-bank members are
  byte-identical. Sound-bank file counts are not individual sound counts.
- `TechTree.plist` is byte-identical. Its original **327 items** (296 active),
  **42 building records**, **56 jobs**, **35 birthstones**, **23 achievement
  records**, and other bundled tables remain present. These are record
  counts, not counts of working/purchasable features; the building table
  includes an unfinished placeholder.
- All five sections extracted into private `local-rules.json` (buildings,
  items, jobs, points-store entries, birthsigns) equal the originals exactly.
  The saved backend-data hashes also match. Other sections, such as
  achievements and dungeon data, remain in the APK but are not thereby
  implemented in the local simulation.

Signature members appropriately changed to the local signing identity.
The archive comparison cannot recover files/rules that the retired service
once supplied but that were never bundled in this APK. It also cannot prove
that every native menu loads correctly.

Machine-readable results:
[meego-offline-core-apk-comparison.json](../evidence/meego-offline-core-apk-comparison.json).
Complete per-member hashes remain private under
`private-analysis/meego/core-audit/`; proprietary game files are not copied
into this report or a public release.

## Confirmed missing or partial offline-core mechanics

These are source/rule-contract findings, not newly reproduced device failures.

| Priority | System | What remains to implement or repair |
| --- | --- | --- |
| 1 | Production buildings | Grub Grub Farm, Quarry and Sawmill have original idle/stock/harvest cycles, but the current building-change handler accepts only `buildable` targets. Normal production-cycle transitions are rejected. Source: `local_game.py:257–268`; job assignment also requires the corresponding active state, `simulation.py:284–285`. Native UI dispatch for each cycle still needs verification. |
| 1 | Production exhaustion and refresh | Harvest stock depletion covers only wild rocks, trees and bushes (types 2/3/4). Industrial harvesting does not consume its stock or advance the necessary production progress; a forced active state could yield indefinitely. Fix the complete cycle together with activation. Source: `simulation.py:142–184,200–214`. |
| 1 | Tools' gameplay effects | Tools can be researched, crafted, bought and equipped, but actual yield reads base STR/INT. Original equipment production/time modifiers, multipliers and job restrictions are not applied. Owning a Chainsaw/Jackhammer/etc. does not establish its intended production benefit. Source: `simulation.py:64–68,155–172`; earlier native catalog audit in `evidence/meego-catalog.md`. |
| 1 | Newborn/newcomer variety and birthstone accessibility | Generated babies and permanent newcomers use the same factory defaults: stats 10/10/10, birthsign `[1]`, and fixed gender-specific appearances. All 35 birthstone records are retained and earned discoveries are preserved, but those population-generation paths cannot introduce the other stones. Parent inheritance/original selection probabilities are unrecovered. Source: `local_game.py:48–57`, `simulation.py:346–350`, `community.py:123–127`, `birthstones.py:53–94`. |
| 2 | Commercial building benefits | Joose/Cawfee-style activation transitions face the same building-state restriction. Current commercial job completion resets the state/job without applying the corresponding boost/reward. Source: `local_game.py:257–268`, `simulation.py:185–191`. Original boost composition remains unrecovered. |
| 2 | Consumable effects and appearance changes | Supported permanent self-target stat items work in the local handler. Temporary/village boosts, scripted effects and appearance-changing consumables lack effect activation. A purchase can be supported while its use effect is not. Source: `skills.py:78–118`; `evidence/meego-catalog.md`. |
| 2 | Achievement/objective rewards and complete progression | Temple upgrades and research exist, but only achievement 102 (temple level) is maintained automatically. Affluence thresholds are placeholders (`current=0`, `next=affluence+100`), and there is no generic achievement/reward evaluator. Tutorial completion only acknowledges tasks. No general earned-crystal-skull reward path was found in the reviewed engine; the legacy migration grant is not an earning system. Source: `local_game.py:71–87,103–104,216–223`; `server.py:193–198`. A separate original XP mechanic has not been established, so no invented XP requirement is asserted. |

An offline completion pass should prioritize production cycles and tools,
then population/birthstone variety, effect-bearing items/buildings and
progression/reward loops. Implementations should preserve saves and use
explicit local policies wherever original formulas cannot be recovered.

## Present, but with balancing/verification limits

- Persistent village save/load, building placement/movement/construction,
  housing and temple upgrades, ordinary wild-resource harvesting and respawn.
- Breeding, fixed nursing/growth deadlines, children/adults/elders and saved
  deathdays; food consumption advances locally.
- Productive-work STR/INT gains, research/tool crafting, supported permanent
  stat consumables, and local Skool/report-card logic.
- Permanent owned newcomers with housing/population limits.
- Original birthstone metadata and additive saved discoveries.

Many rates are restoration choices, including resource stocks/respawn,
food per resident, age scale, work-stat threshold and newcomer cadence.
Exact original genetics, production/equipment composition, hunger/mood
consequences and achievement rewards are not established by this audit.
Existing backend tests do not certify every native animation/menu. In
particular, Rabbit's previously blank detail popup, school/report refresh,
all shop effects and every building/job transition remain unverified in the
native client. Preserve that distinction when reporting completion.

The earlier private-APK catalog checks exercised 49 of 50 shop entries at
their bundled price/recipe. Turtle Topper (371) has neither a positive
purchase price nor a resource recipe; no free grant or invented price was
added. Its unavailable purchase method is a catalog ambiguity, not proof a
file was lost. Some inactive/event records likewise are not required core
shop purchases.

## Tourists versus permanent newcomers

The original contracts identify tourists as visiting other players' villagers:

- Original `jobs/0` has remote name `TOURIST`.
- `JMVillager.isMyVillager` (`0xa51adc`) compares ownership; the travelling
  check (`0xa51c84`) compares owner and location IDs.
- The travel client (`0xa38efc`, request at `0xa391e8`) sends `to_user_id`.
  The Launch Dock's bundled description connects travel to other villages.
- Native strings distinguish visiting Meego from local Meego for breeding.

No independent NPC tourist-spawn contract was recovered in the bounded
existing analysis. Real-player tourists and their social travel rewards are
outside the requested offline-core target. An offline NPC tourist substitute
would be new local behavior and has not been implemented.

**Permanent offline newcomers do exist.** Read-only saved-state inspection
found three recorded local arrivals, six owned Meego and zero other-owner
guests. This establishes saved arrivals, not observation of the landing
animation. Current policy permits one eligible owned adult per six real
hours with housing/population limits; the original cadence is unknown.

CHR's original work progression is tied to Launch Dock travel. Current local
work growth covers STR/INT; supported permanent consumables can raise CHR.
If full offline access to every stat/collection is required, a documented
offline CHR progression route should be considered without restoring online
social services. See `community.py:70`, `skills.py:55,78` and the retained
private arrivals/skills findings for exact native evidence.

## Other content classification

Real accounts, remote villages, other-player gifts/visits, messaging,
leaderboards, payments and online events are excluded, rather than blockers
to this offline island target. The treasure mini-game is currently deferred,
quest/task lists are empty, and dungeon/adventure mechanics are not restored.
Their retained assets do not make them playable. They should be separately
classified if the offline target expands to include solo adventure/mini-game
content; do not silently describe those systems as complete or add online
dependencies to provide them.

No further game patch or installation was made for this audit.
