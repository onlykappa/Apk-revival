# Temple hunger and closed-game food policy — 0.3.23

Requested policy: hold the food balance when Meego is closed. Food harvesting
and food consumption pause over closed intervals. Wood/stone gathering, aging,
respawns and production preparation retain existing offline behavior. Food trips
resume on return without discarding accumulated partial work or using up bush /
farm stock while food is frozen. No supplies are refilled or refunded.

## Hunger repair

The saved food bank was positive (390 during the initial read), but native
`global_state.mood_state` was the starter0 and was never updated by food logic.
Offline original-library inspection recovered:

- JFVillageService.villagerIsHungry:0x8f6b60 and villagersAreHungry0x8f6bf0
  read global_state.mood_state and return true when it is below2.
- JFTempleHead.playAnimationSequenceForMood:0x8360dc selects neutral for2,
  unhappy for1 and mad for0. JFVillageService.villageMood reads the same model.

Local policy now publishes2 (fed/neutral) for positive food and1 (hungry) for an
empty bank, after actual consumption and after later food gathering. This is a
stocked/empty restoration rule, not a recovered former-server threshold system
or permanent happiness/production boost. No native APK patch is needed.

## Session handling

Food policy is local-resident-food-active-session-v2. v1 save accounting migrates
without food debit or refill. Fractional active minutes are preserved. Backend
startup and native login/resume establish a fresh food charge baseline without
moving the world's last_simulated_at forward. First-request offline catch-up,
logout/paused polls and reconnect/resume suppress both consumption and food
harvest credit. Source stock is not depleted and work XP is not granted for
paused food trips. Once active, normal per-minute charges and food trips resume.
A crashed host process gets the same protection on next startup.

The rate remains the existing local one food per owned, present, living resident
per active minute; guests, dead and away residents do not charge home food.
Native rate units remain per minute. Other timers and saved village progress
are preserved. Finishing a paid recipe or collecting a reward while playing can
still explicitly change food; this policy freezes passive closed-time changes.

## Verification scope

Temporary-save tests cover positive-bank hunger repair, empty/refilled changes,
legacy migration, minute/fraction conservation, logout/background polls/resume,
unclean restart, first request without login, preserved offline baby growth,
food bank/source stock freeze with assigned gatherers, and simultaneous offline
wood production. Live data was read into memory to check a24h baseline reset:
505 food stayed505, mood0 became2, the world clock stayed unchanged. No live save
was written by that check. After installation, the user reopened Meego and confirmed the hunger message
stopped. Live state showed positive food, mood2 and the v2 policy. Closed-time
food freeze passed automated session/restart tests; no manually timed closed
interval is claimed.
