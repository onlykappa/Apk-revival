# Meego integration: observed results

Date: 2026-10-12. Software: APK Revival 0.3.0. Original APK hash is recorded in MEEGO.md. Private APKs, recovered rule tables, diagnostics and saves are not committed or included in the application release.

## Real files and tools

The supplied executable Meego v1.32 APK was imported and analyzed through the V2 service and actual Qt interface. The reviewed native instructions, compiled package/label strings and local endpoint settings were patched on copies. Actual Android SDK alignment/signing tools verified the result. Original bytes and hash remained unchanged.

The actual local HTTP service exercised login/village response shapes, building placement, rejected unknown actions, persistent village state and backend restart. Save backup/restore retained a previous backup before replacement. Portable export contained the signed client and required private backend data, and excluded signing keys, originals, logs and private saves.

A deliberately wrong native patch precondition failed without replacing the previously prepared APK. A real occupied TCP port caused startup failure; releasing it allowed recovery. Health identities changed across service starts. Only host loopback was used for these service checks.

## Interface and verification logic

Actual Qt widgets exercised Meego import, preparation, honest missing-Android readiness and cancellation of the guided test. The cancel-path signal conflict discovered during testing was fixed and the regression test passed.

The full guided workflow is implemented, but its positive Android gameplay path has not been executed in this environment. A command-boundary double verifies that firewall cleanup is attempted even if game stop raises an error. This is a cleanup logic test, not evidence that Android firewall commands ran.

The local combined suite includes V1/V2 tests and the opt-in Meego APK integration tests. Observed local total: 60 tests, 58 passed and 2 optional legacy Tk tests skipped. This combines the 58-test engine/interface suite with two additional private-rule simulation tests. Fixed-clock simulation tests exercise gathering/caps/depletion, worker construction, breeding idempotency, aging and restart; these are host service checks, not native UI proof. GitHub CI cannot run the private Meego APK tests without those files; it runs the reusable fixture and source tests and explicitly skips private-file integrations.

## Not run on Android

No new Meego Android cold launch, rendering, gameplay action, guest save/relaunch, guest-to-host reachability or guest network-blocking check ran here. No Meego profile was marked Verified Offline. Earlier user-reported Deck behavior belongs to the earlier Meego client and service package, and is retained only as prior evidence.

This environment exposes no Binder devices, Wayland session or KVM device and has an empty root capability bounding set. A Waydroid userspace package cannot remove these host limitations. Use the existing compatible Waydroid environment on the Steam Deck for the guided test.

## Remaining Deck checks

Run Game options > Advanced > Test offline now after successful Prepare and Setup. Confirm village/menu interaction, a new building purchase/upgrade, saved progress after client/backend restart, and recovery after intentionally stopping the backend. The test records the observations alongside runtime/network evidence, binds results to the exact prepared APK hash and restores owned rules on completion/cancellation.

Physical controls, Gaming Mode, ARM translation, untested mechanics and full original feature parity remain outside the observed test scope.

