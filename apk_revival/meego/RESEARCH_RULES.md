# Thinking Rock progress and construction staffing

The original native `JMVillageClient.getResearchProgress:` at 0xa3b1c0 sends
`game/village/get_research_progress/`. Its `JFUIResearchBuilding` success
callback at 0x69ef9c–0x69f128 reads `max_out`, `researching` and `progress`
directly from the response. The progress float scales the original progress
bar; the booleans distinguish available ideas, temple-limited ideas, and all
items invented. Returning an exception for this read broke the native menu.
The offline responder now supplies that direct packet.

Research job20 already credits resource4 (original counter-unit372), using
the existing local work-rate policy and intelligence modifiers. The existing
`game/purchase/unlock_item` action checks original research cost, temple level
and prerequisite item, spends research points once, and persists native
research cursors. No unlock or points are awarded by reading the progress UI.

The progress display uses an explicit LOCAL selection policy: progress toward
the cheapest active, unresearched item whose temple and prerequisite checks
currently pass, clamped to0..1. `researching` means such a recipe is available;
`max_out` means all active research recipes are already unlocked. This is a
useful offline display, not a recovered original-server research scheduler.
Reaching a full bar does not auto-buy a tool or change an existing selection.

Storage type8's original construction state has active job5, zero housing
slots, and no `max_workers` field. The previous assignment fallback treated
housing slots as builder capacity, rejecting every builder. Construction now
uses one builder when an explicit worker limit is absent. Explicit limits
remain enforced; housing capacity and permanent staffing are unchanged.
Existing construction timing and storage capacities are retained.

Regression checks use the privately owned original APK read-only and temporary
villages: Storage assignment, second-worker rejection, restart/completion and
capacity increase; Thinking Rock work earning research points, native progress
request parsing, no mutation from display reads, temple/finished-catalog flags,
original-cost research unlock and replay without an extra debit.
