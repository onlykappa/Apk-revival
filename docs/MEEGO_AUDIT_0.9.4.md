# Meego audit: 0.9.4

Scope: offline aging/session boundaries, growth/death and native timers; node
stock, carry, caps and respawns; building movement/deletion and native model
projection; production, school, travel/adventure and item-effect integration.
This is a source and regression audit, not an on-device visual certification.

## Confirmed and fixed

| Finding | Effect | Correction |
| --- | --- | --- |
| Structure and manual resource deletion lacked removal markers | Merge-only native cache could retain ghost graphics | Send bounded explicit null deletions, excluding IDs currently reused |
| Jobs referenced removed sources or depots until another poll | Worker animation could continue after deletion | Idle affected workers in the deletion response |
| Moving nodes lost the capacity record's ID/location association | Next synchronization could add the capacity increase twice | Move the record with the node, including same-ID position changes |
| Mods displayed the old six-node cap | UI disagreed with the five-node rule | Correct label and select current burg stock for respawns |

The new aging feature also keeps growth skip-token generations stable when
birthday shifts, and keeps owned adventure render snapshots consistent.

## Validation and limits

The five model/move regressions fail on the 0.9.3 base and pass with this patch.
Aging coverage includes a day away, longer absences, active play, JSON reload,
repeated timestamps, rollback, nursing growth, dead/guest exclusion, session
restart, logout/resume and adventure date projection.

Full local suite: only three existing runtime-access errors caused by the root
execution account. Excluding that module, 681 tests pass (176 skipped).
Private original APK and GUI fixture tests are skipped.
The exact graphical glitch reported by the user cannot be identified without
seeing it on the Deck; ghost-model fixes address confirmed state defects only.
No speculative native binary patches or art replacements were applied.
