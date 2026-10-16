# V2 architecture and runtime boundaries

V2 is a native PySide6 interface around the V1 Python restoration engine. It uses the existing Store, analysis, Restorer, Saves, exporter, backend and verification modules. V1 CLI commands remain available; the former Tk interface is `legacy-gui`. Core CLI analysis needs no Qt, cloud account or paid service.

## Ownership and persistence

`launcher/service.py` orchestrates import, preparation, launch, stop, saves and exports. `jobs.py` serializes mutations on worker threads and exposes actual named stages, failures and safe cancellation checkpoints. Profiles and hash-bound plans remain V1's authority. Readiness is derived independently in `presentation.py`: importing an unknown game never makes it playable. Rebuild progress never certifies the original APK.

Private originals, profiles, signing keys and saves remain under the Store root, normally `~/.local/share/apk-revival`. Tool downloads stay under `~/.cache/apk-revival/tools`. An application update replaces only the user-owned application folder and preserves its predecessor. Diagnostics summarize evidence and exclude originals, private saves, signing material and raw logs.

Native exports carry a replaceable one-directory application runtime and a single-game interface. Hashes detect package corruption; they are not publisher authentication. Portable saves have a separate per-game location. Android exports still require an Android environment and connection tools. Source-only exports retain the V1 Python launcher.

## Runtime adapter

V1's `WaydroidRuntime` remains the Android command boundary. V2's RuntimeManager detects host status and guest IP, connects available ADB devices, requires explicit selection when multiple devices exist and starts only supported sessions. ManagedAndroid checks API/ABI compatibility and hashes the installed base APK before reinstalling. OBB deployment receipts are per device. Re-signing signature conflicts are reported without silently removing installed games.

The local backend binds loopback and uses ADB reverse with a unique health nonce checked from Android. Host HTTP success alone cannot establish guest reachability. Stop removes only owned forwarding, backend and selected game processes. The container is shared and is not terminated by APK Revival. A session started by the launcher is tracked separately.

Waydroid installation cannot be treated as a generic SteamOS package install. The launcher checks Wayland, binder support, tools and session state; it offers a guided host installation link. The only privileged button reviews the concrete `pkexec systemctl start waydroid-container.service` action and delegates authorization to polkit. It never changes SteamOS read-only protections or records passwords. ARM translation is a separate runtime capability.

Current references inspected during implementation:

* [Official Waydroid desktop installation](https://docs.waydro.id/usage/install-on-desktops): Wayland and distribution prerequisites.
* [Official Waydroid command line](https://docs.waydro.id/usage/waydroid-command-line-options): container/session/status operations.
* [Waydroid status implementation](https://github.com/waydroid/waydroid/blob/main/tools/actions/status.py): reported session, container and guest IP.
* [SteamOS Waydroid community bundle](https://github.com/pjohno/steamos-waydroid-bundle): SteamOS-specific route offered as an external community guide, not bundled or automatically executed.

Actual Steam Deck hardware, Gaming Mode compositor behavior, ARM translation and guest firewall capabilities remain unverified in this build environment.

## Interface and controls

`ui.py` provides library cards, local generated artwork, selected-game actions, real background jobs, setup and Advanced evidence views. Qt handles touch, mouse and keyboard. `controller.py` uses SDL2 GameController polling with visible focus, focus-aware input, directional scoring, deadzone and repeat timing. Confirm activates the focused button; Back closes dialogs or returns from the rebuild. F11 toggles fullscreen.

Launcher navigation does not map controller input into arbitrary Android games. The fixture's original Android client needs touch or mouse; its independent desktop rebuild supports confirm on Collect. Additional games need adapter-defined control guidance or a suitable Android input layer.

## OmniPC reuse

OmniPC was inspected read-only. Its MIT license permits adaptation and is retained in `resources/OMNIPC-LICENSE.txt`. We adapted spatial focus scoring, focused controller handling, named job stages and launch ownership patterns from `src/renderer/lib/{gamepad,spatial}.ts`, `src/main/core/jobs.ts` and `src/main/launching/launchService.ts`. Library and diagnostic views informed the interface. Windows-specific launch services, Electron dependencies, console categories and account features were not copied. OmniPC was not modified.

## Adding a game adapter

Start with [ADAPTERS.md](ADAPTERS.md). Supply exact APK/version evidence, explicit reversible operations, backend contracts or rebuild feasibility, asset placement and save locations. Add meaningful gameplay verification, not only endpoint replacements. V2 consumes these services through the orchestration layer; game-specific logic belongs in adapters and the engine. All three fixture workflows are implemented; none implies automatic restoration of unknown games.

## Meego adapter in 0.3.0

Meego adds a bounded binary-operation type restricted to reviewed native/compiled targets for the exact original APK hash. Backend code is trusted source; rule tables are extracted from user-owned assets into private working copies. Prepared client package metadata is separate from original metadata so prior installs stay intact. Saves, runtime lifecycle and native/source exports support this local-backend adapter. Its guided verifier records explicit user observations plus Android/network/service evidence and refuses a passing claim without the required checks.

