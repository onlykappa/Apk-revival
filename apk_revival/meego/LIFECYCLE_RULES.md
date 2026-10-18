# Death, revival and Return to age 20 (0.9.5)

## Native integration

The original reviewed Meego 1.32 library contains:

- JFUIVillagerDetailMenu.onResurrect (0x761730), which opens
  JFUIResurrectPopup for the selected owned villager.
- JFUIResurrectPopup.onResurrectFree (0x7ff4b0), which sends the existing
  resolveDeadVillager:shouldResurrect:withSkulls:withCallback: service call.
- The service implementation (0xa3af7c) calls
  game/village/confirm_dead_villager/ with villager_id, alive and use_points.
  alive=true restores; alive=false is the explicit tombstone-clear action.
- The callback binds the direct home game-state response, then posts the existing
  resurrect_success notification to refresh the native villager display.

The patch recipes in lifecycle_mod.py add a real onResurrect control below the
age icons in both original stats layouts. The existing popup becomes a single
free Return to 20 confirmation with All stats kept text. The paid/partial-stat
choice is hidden and disabled. No new Objective-C selector or native code cave
is injected. Original asset SHA checks and exact CCBI round trips are required.
Animation blocks are retained unchanged; original assets do not ship in source.
The native_lifecycle_mod plan revision triggers normal Play's existing one-time
preparation/install update, using the existing original and signing identity.

## Local lifecycle policy

Revival and manual rejuvenation are free and preserve base stats, equipment,
appearance, birthsigns, identity, village balances and delivered-work progress.
Birthdays become now minus twenty age units. Deathdays preserve at least the
normal hundred-unit lifespan and retain longer individual lifespans. Existing
closed-session aging remains half speed after the action.

Living Meego must be owned, home, and at least twenty. Their active job and
partial-trip accounting are preserved. Dead Meego revive idle; stale quest and
dungeon quest pointers are cleared, and model timestamps are refreshed. A
short persisted receipt makes immediate duplicate callbacks idempotent.

The existing Free up space action still requires its native explicit confirmation
and only accepts a dead owned home villager. It sends a bounded explicit null
removal to the merge-only native cache, releases nursing references, and removes
the cleared villager's skill remainder so a reused ID cannot inherit it.
Removal markers never delete reused IDs or touch remote/dungeon views.

## Verification scope

Tests cover elder-to-20 preservation, death-to-20 revival, retry/restart, invalid
flags, living/guest/away rejection, tombstone removal, native cache projection,
phone/tablet controls, exact original animation retention and package inclusion.
The private original APK and final signing checks are exercised locally.
Actual animation/touch behavior on the Steam Deck remains hardware verification.
