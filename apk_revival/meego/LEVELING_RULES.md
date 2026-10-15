# Village level and Temple progression

The original rules distinguish Temple achievement102 (caption Temple Upgrade!,
Temple Upgrades, maximum14) from the village-information affluence/level fields.
The offline implementation accidentally copied Temple level into both village
level fields, while moving their progress bar between affluence milestones.
The bar and level number could consequently disagree indefinitely.

Village display level now follows the same milestone interval as its affluence
bar. This uses the existing explicit LOCAL schedule based on original completed
Temple-affluence values, extending the final interval above the last value.
This is a coherent offline display policy, not a recovered original-server XP
formula. All original building/research unlocks still use Temple achievement102.
Population capacity, storage capacity, currencies and item grants are unchanged.

Temple level still advances only after a valid original upgrade finishes.
Original costs, valid next states and construction gates are retained. There
are14 original Temple levels; no additional Temple state is invented.
For example, level6->7 requires90000 stone,180000 wood and2200 gold. A shortage
rejects the upgrade atomically. Construction of state60 retains achievement
level6 until the worker completes it and enters state61/Temple7. A village
number above6 cannot bypass this requirement or research temple-level gates.

Tests supplied with the source use the user's original APK read-only and
fresh temporary villages. They exercise every Temple upgrade1->14, a single
missing resource, invalid level skips, construction/restart, the village6->7
threshold, matching user/village display fields, and retained Temple/research
gates with no resource or building changes from recalculating the display.
Real review affluence25459 maps to village13 under this LOCAL schedule while
its actual completed Temple remains6. This reflects the existing funded test
village; the test supplies/population are not transferred to the main village.
