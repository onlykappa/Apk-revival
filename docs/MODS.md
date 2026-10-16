# Optional Meego mods — 0.3.22

Open a baby/nursing, child, or building/production countdown inside Meego.
**Skip timer** sits beside the panel's X. One click finishes that selected
supported task without charging skulls. Stay in the game; no launcher switch,
reset or global fast-forward is needed. Timers run normally until clicked.

The user confirmed the in-game Skip timer worked on the Deck after installing
0.3.22. This confirms the exercised native path; it does not certify every
building phase or menu. Automated checks cover baby/parent, child, construction,
production preparation, stale retries, zero balances and save/restart.

The native mod reuses the original bound completion button and callbacks. Its
normal disable/enable logic still guards repeated clicks. The paid store panel
is hidden in the three reviewed countdown classes. Price and confirmation
changes are exact-byte patches to the reviewed original library; the panel
operation requires its exact hash. Only a prepared client carrying timer-mod
revision1 enables the corresponding backend route adapter. Unmodded clients
retain the existing paid completion path. No purchase or remote server is used.

## Optional launcher picker

APK Revival -> select the running Meego entry -> Mods still provides additional
selected-task skips. **Enable launcher timer picker** only enables that optional
picker. It does not control or automatically use the in-game Skip button.
Choose a timer explicitly and press Skip timer. New tasks appear automatically;
expired selections are cleared rather than silently replaced with another task.

The picker supports:

- Assigned construction/upgrades and Farm/Quarry/Sawmill preparation. Finishing
  preparation creates normal finite stock; villagers still harvest it normally.
- Skool classes, with the normal single local class result and report collection.
- Baby to child or child to adult, one stage per click. Nursing ends after the
  baby becomes a child. Other people and absolute death deadlines stay unchanged.
- Recorded item cooldowns, without activating, extending or duplicating buffs.
- Next resource respawn, retaining safe-site occupancy and six-per-kind caps.
  Each click spawns at most one missing tree, bush and rock using normal ecology.

The native shared panel covers baby, child and building countdowns. Classes,
item cooldowns and resource respawns are currently picker-only. Research requires
research points, not a separate countdown. Dungeon actions, commercial service
expiry, arrivals, death, reward collection and active buff duration are unchanged.

A picker refresh reads metadata rather than re-hashing APKs on the UI thread.
State-lock acquisition is bounded to50ms; a busy service reports a retry rather
than blocking the launcher indefinitely. Refresh does not write a save. Actual
skips use the existing backend lock, atomic persistence and backups. The last100
mod actions are recorded in local_mod_history. A completed skip is not undone
by closing a menu. Ordinary Play does not invoke any skip action automatically.
