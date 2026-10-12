# The Meego: first real-game adapter

Supported input is The Meego v1.32, original package `ata.squid.meego`, SHA-256 `030613cbc63bd03786545999c3590456a264796866127898928a4d59988d29a2`. Other APK versions do not silently use these patches.

This is the local-backend path. Standalone offline APK and separate rebuild workflows are not implemented for Meego. The native game and assets remain in the APK. The earlier experimental responder was self-authored from observed client expectations and recovered bundled rules; it is not recovered original server code or full feature parity.

## Use it on the Deck

1. Install APK Revival 0.3.0 and connect your existing Waydroid through Setup.
2. Add the original `The+Meego_1.32_APKPure.apk`, then Prepare. The app handles patches, alignment, signing and private local-service configuration.
3. Play. The separate Android application is named **Reviv**, package `ata.apkrv.meego`. It leaves the original game and earlier Local/Fresh installs intact. The launcher starts an owned loopback backend and checks Android-to-host reachability using a fresh nonce through ADB reverse.
4. Game options contains Backup Save, Restore Save and Export. To import an earlier village, attach exactly one `village.json` as a **Save file** before preparation. It is copied only if the launcher has no current village save; an existing launcher save is never silently replaced. Do not expect the older Meego launcher's host save to be adopted without selecting it.
5. To test offline gameplay, choose Game options > Advanced > Test offline now. Follow the guided confirmations while interacting with Meego in Android. The test temporarily blocks external guest connections and restores only its owned rules when finished or cancelled.

Waydroid must support the original 32-bit ARM native library, through compatible ARM support/translation where necessary. Android version, rendering and native bridge behavior need testing on the target device. A package can be signed successfully and still fail to play.

## Exact reviewed changes

* `lib/armeabi/libverde.so`: same-length ARM instruction patches at offsets `0x8e32f0` (`0xe1a05003` → `0xe3a05000`) and `0x8e330c` (`0xe59b8008` → `0xe3a08001`). These select HTTP with an explicit local port. Each operation checks the entire member hash and original instruction bytes.
* Compiled Android manifest: same-length package substitution, avoiding signature conflicts with earlier installs. Version is preserved. The app label is changed to Reviv with same-length compiled string replacements.
* `assets/Info.plist`: local endpoint and identity fields route to guest loopback. The launcher creates owned ADB reverse forwarding to its host loopback service. It never assumes Android localhost is the host.
* `assets/TechTree.plist`: buildings/items/jobs/point-store rules are extracted into private working data. No recovered game-rule table or proprietary asset is committed or shipped inside the app.

All archive changes are explicit, hashed and reviewable under Advanced. Original files are read-only copies. Failed patch preconditions preserve the previous prepared artifact. Preparation generates a fresh signed APK; it does not use or distribute the earlier private signing key.

## Local service scope

The service supports documented local resource spawning/gathering, building placement/movement/upgrades, workers and construction timing, local currency purchases, provisional breeding/aging/food simulation and persistent village state. Construction and progression rates are assumptions, retained from the experimental earlier service. Unsupported requests return explicit errors. No real payments, original accounts or upstream network calls are performed.

Quest chains, social/multiplayer features, treasure behavior, original economic balance and some visual effects are incomplete. The API can persist an action correctly while the native UI handles it differently. Android checks are therefore necessary.

The earlier user reported village rendering, menus/zoom, resources, building purchases/upgrades and level-four temple progress saved on Steam Deck. Those observations concern the earlier package and transport. They do not certify this new client, package, signature or ADB-reverse configuration.

## Guided verification evidence

The test records cold launch and visible village/menu interaction, a successful new building-action request, saved state, restart of the game and backend, visible loaded progress, deliberate service failure and recovery. Human confirmations are explicitly labelled user observations because the native OpenGL UI lacks reliable text automation. Host-side HTTP results alone never satisfy the gameplay checks.

Verified Offline requires every check, enforced IPv4/IPv6 guest restrictions, negative external probes, an unchanged prepared artifact and successful cleanup. Unavailable root/firewall capabilities refuse certification. Cancelling records an incomplete test. The scope excludes untested mechanics listed above.

## Build-environment limits

The build environment has no Binder devices or Wayland session, and its root capability bounding set is empty. Installing userspace Waydroid cannot supply the missing host privileges/kernel devices. There is also no `/dev/kvm` for a hardware-accelerated emulator fallback. No new Android gameplay test was run here.

See [MEEGO_TEST_RESULTS.md](MEEGO_TEST_RESULTS.md) for observed tests and the remaining Deck checks. Private diagnostics and saves remain outside GitHub.

If the process is forcibly killed or Android disconnects during cleanup, networking may remain blocked in that guest. In-progress verification records retain the exact owned chain and serial under the private game directory. Use the existing [verification recovery instructions](VERIFICATION.md); never flush unrelated firewall rules. Normal cancellation, closing and termination request orderly cleanup.
