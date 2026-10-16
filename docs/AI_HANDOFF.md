## Fullscreen follow-up — October 15

User confirmed Lowsee has a normal countdown and has become a child. This is
physical confirmation of the previous baby timer/growth fix.

New game_window.py requests fullscreen on KDE Wayland only for the exact
Waydroid game app_id (waydroid.<package>), both existing and newly opened normal
windows. Play installs a transient KWin script before activity launch; stop
unloads that script. No permanent KDE rules, resolution, input mapping or saves
are changed. Existing Android immersive policy remains package-scoped. Phone
ADB devices and Gaming Mode do not receive KDE requests. Host D-Bus is blocked
inside the development sandbox; actual fullscreen must be confirmed via normal
Play outside the sandbox. The UI title bar and KDE panel in the user's photo
were desktop presentation, which Android immersive settings cannot remove.

The updated package remains version 0.3.20 (fullscreen hotfix). Candidate:
dist/APK-Revival-0.3.20-fullscreen-candidate. Executable SHA256:
a74636b55010fb83dc9b0ef86ec8f88acda09d0f96b053caaf7471ac866ccf51.
253 packaged tests passed, including all five new fullscreen checks.
Prior harvest archive below predates fullscreen. Initial JS test required
QtQml absent from the minimal bundle; the corrected test executes real JS using
the Deck's existing Duktape library. Runtime preflight ordering test now isolates
privilege routing instead of assuming the optional helper is absent.

Offline timers already use saved timestamps and catch up on reopen; no network
or always-running Deck is needed. Work/food catch-up is capped at 24 hours;
birthdays remain absolute dates (2h baby, 10h adult under current local policy).
Construction, production and solo-adventure stages still require their normal
assignments/resources/claims. This is local restoration policy, not recovered
proof of original server balance.

The password-free runtime helper and sudoers file now exist on the host;
actual unattended cold-start/reboot success is still unverified here. Do not
interpret sandbox sudo failure as proof the host helper failed.

---

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

121 original-rule Meego source regressions passed;100 related checks passed
(52 aging/trip/simulation/skill plus48 effect/production/wire/ecology);
248 packaged launcher/gameplay tests passed
without source overrides. The earlier merged build also passed offscreen Qt
preview at1280x800 and1000x650 and actual archive staging/probe checks.
The final gameplay hotfix rebuilt successfully, passed its packaged suite, and
passed actual archive extraction/staging plus the child version/certificate probe.
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
