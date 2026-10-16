# Deck integration handoff — 0.3.20

Use `deck-0.3.20-launcher-meego` for the complete merged launcher, gameplay,
build scripts, tests and documentation. `deck-0.3.19-meego` retains the game
patch export; its latest gameplay fix commit is
`df0ff6eec648e1c122a793b0d4e7eaeea491dad7`. No GitHub main merge or public
release has been performed.

The upstream launcher release is v0.3.8, commit
`775d190baf4477e3e1491435b1e0f77fb1add98d`. Its design was merged with the
working Deck branch, retaining diagnostics, recovery, original APK importing,
three restoration paths and existing gameplay/camera controls.

## Latest fixes

- The596523:14:07 infant timer is INT_MAX seconds. The native NSDate binder
  requires decimal JSON numbers. Aging stored integral last_update values;
  wire projection now emits decimals without altering birthdays/deadlines.
- Exhausted trees, bushes and rocks send explicit null deletion markers to
  the native merging model. Server-side final pickup was already conserved.
  Markers are bounded, restart-safe, skip live reused IDs and exclude dungeons.
- Requested base carrying capacity is2 for stone/wood/food. Existing skill,
  tool/boost bonuses, stock conservation and60 delivered-unit stat threshold
  remain. Research retains base1. This is documented local balance.
- Portable export packaging includes the project .py files it needs instead
  of assuming synthetic PYZ module paths are real source directories.
- Long title/package labels no longer stretch/clamp the details controls.

## What actually ran

121 original-rule Meego source regressions passed;52 related aging, trip,
simulation and skill tests passed;248 packaged launcher/gameplay tests passed
without source overrides. The earlier merged build also passed offscreen Qt
preview at1280x800 and1000x650 and actual archive staging/probe checks.
The final gameplay hotfix rebuilt successfully and passed its packaged suite.
Physical timer/resource cleanup confirmation after reopening is still pending.

On this Deck, full launcher0.3.20 is installed at
`~/.local/share/apk-revival-app`. All17 protected save/profile/APK files were
hash-identical before/after replacement. The existing live island was NOT reset.
The earlier requested fresh start has since gained a baby: preserve that save.
Installed executable SHA256:
`d7a11c893a6104512cdd968799b940d2d3b6c86b15564d366dd93dccc8da4573`.

Local integration checkout:
`/home/deck/Apk-revival-merged-0.3.19-v0.3.8`, branch
`merge/launcher-0.3.8-meego`. Current candidate is
`dist/APK-Revival-0.3.20-harvest-candidate`; current installable tar is
`dist/APK-Revival-0.3.20-linux-x86_64.tar.gz`, SHA256
`3b3741d376629043bd5f722bf375dcba9baf0d0f9d99c43def3abec4d9d76b37`.
Old candidates/archives remain but lack the final fixes. Build receipts and
test logs are local under build/, and are not private-data uploads.

## Password-free startup: prepared, not yet host-verified

Setup -> Enable password-free startup requests one final administrator
authorization to install a root-owned helper with exactly five fixed main
runtime actions. No password-free shell or user-controlled script is granted.
See RUNTIME_ACCESS.md. The sandbox cannot elevate (no-new-privileges), so this
system configuration has NOT been installed by the agent. The user must use
the host Setup action, then test cold startup, a second launch and reboot.
Do not claim that repeated password prompts are gone until that check passes.

Waydroid remains the actual Android runtime; APK Revival manages it. No Android
reset, security disabling, system firmware/partition change or save deletion.
All APKs, user saves, signing keys and private raw native evidence are excluded
from GitHub. Original binary analysis used private files and offline LLVM/ELF;
the tests reference a user-supplied APK via APKR_MEEGO_APK.

Next: verify finite infant countdown (a new baby is the clearest check), final
node disappearance, two-unit pickups, and password-free host startup. Preserve
the current island. See OVERNIGHT_HANDOFF.md for full chronological evidence.
