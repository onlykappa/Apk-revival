# Final resources, carrying capacity and baby timers

## Native date contract

The original Meego1.32 JMBinding NSDate conversion checks NSDecimalNumber before
converting its integer seconds to a date (0x83a880–0x83a8f0; class relocation at
0xbf5d20). A JSON integer is not that decimal-number class. Aging deliberately
keeps whole-second job clocks in the save, but sending those as JSON integers
leaves JMJob.last_update unset. JMJob.expire_date then returns distantFuture
(0x8a8c9c–0x8a8df0). The nursing popup reads that expiry (0x7b3c74), producing
the reported saturated596523:14:07 (2147483647 seconds).

The HTTP projection now emits integral last_update values as JSON decimals,
e.g.123.0. This changes neither saved birthdays nor job deadlines. The existing
local policy remains one real hour per age year: baby becomes child at age2
(two hours after birth), child becomes adult at age10. Repeated polls/restarts
must not restart these deadlines. Tests cover the native JSON number type,
fixed expiry, releasing the nursing parent, and both growth boundaries.

## Final resource deletion

The simulation already credits the final available unit exactly once, removes
the exhausted node and releases its workers. The original native model binding
merges dictionaries; omission alone leaves the former tree/bush/rock cached at
its last stock count. Keep up to512 depleted-node ID markers outside game_state
and send explicit null deletions in home-island building maps. Markers survive
save reload, never award resources, skip currently reused IDs, and never affect
dungeon maps. Replenishment continues using the existing known-site policy.

## Requested carrying-capacity adjustment

Basic stone/wood/food jobs16/17/18 now start at TWO units per completed trip,
instead of one. This is a requested local balance change, not a recovered
original-server formula. Existing strength/tool/effect bonuses still apply;
research keeps its separate one-point base. At STR11 the unboosted rate is2.01;
fractional yield accumulates across trips. Existing original tool modifiers and
the local five-unit unmodified cap are preserved.

Work stats still gain one point per60 units actually delivered. Full storage
cannot accumulate deliveries or stat credit; final partial trips take only the
remaining stock. No existing resource balance, inventory, skill, birthday or
save is reset, and no retroactive doubled reward is granted.

Verification:121 original-rule source regressions and52 related timing, trip,
simulation and skill checks pass. Native on-screen confirmation is pending the
updated launcher restart. Static evidence came from the privately supplied
original libverde.so using offline LLVM/ELF analysis, not a live REA capture.


## Resource abundance policy (0.9.3)

Wild trees, rocks and bushes each start with 250 material at completed burg
(Temple) level 1 and gain 50 capacity per completed upgrade. Standing nodes gain
only the capacity difference; depleted nodes never refill. Native placement and
local respawns share the same capacity and a limit of five per type. Respawn
checks run on active simulation requests every 60 seconds, adding at most one
missing node of each type per check at known unoccupied sites. No backlog is
replayed after inactivity. Existing sixth nodes are preserved until harvested,
then cannot be replaced while five remain. Production buildings retain their separate stock rules. Resource carrying
capacity for jobs 16/17/18 is now 20 + max(0, STR-10)/5, including eligible tools
and effects exactly once; research uses its original INT formula.
