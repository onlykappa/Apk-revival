# Optional Meego mods

In APK Revival 0.3.21, select your existing Meego entry and press Play. Switch
back to APK Revival while the game is running, then select **Mods** below
Game options. Check **Enable Skip timer**, choose a task, and press **Skip timer**.
The switch starts unchecked whenever the menu opens. It enables the button;
it does not change timer speed or skip future tasks automatically.

The picker shows active, supported tasks:

- Construction and building upgrades with an assigned builder.
- Farm/Quarry/Sawmill production preparation with an assigned worker. Finishing
  creates the normal finite output stock; villagers still collect it normally.
- Skool classes. Completion grants the usual single class result and leaves
  report-card collection in the original game menu.
- Baby to child, or child to adult, one stage per click. Nursing is released
  when the baby becomes a child. Other villagers and death deadlines stay put.
- Item cooldowns. Skipping does not activate the item, award another buff,
  restart an existing buff, or create another copy.
- The next resource respawn. Existing sites, occupancy checks, normal stock
  quantities and the six-tree/six-bush/six-rock caps still apply. At most one
  missing node of each type is spawned per click, using the normal ecology code.

Press Refresh timers after starting a task. Listings are snapshots; a task that
finishes, changes state, or moves before the click is rejected with an explicit
refresh instruction. The game receives the result on its next ordinary state
update; close/reopen the selected native panel if it still shows an old timer.

This version does not add buttons inside Meego's native Android menus. Research
is based on earned research points, not a separate countdown, so it is not
listed. Dungeon actions, commercial service lifetimes, arrivals, death,
reward collection and buff duration are not accelerated by this mod.

No global clock fast-forward, fake offline interval, free purchase, automatic
cheat on Play, new server connection, APK reinstallation or save import is used.
The selected change is applied under the running backend's lock, saved by its
existing atomic save/backup routine and recorded in `local_mod_history` (last
100 actions). Closing Mods does not undo a completed skip. Test this on a
selected task deliberately; ordinary Play remains unchanged without using it.
