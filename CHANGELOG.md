# Version history

Product milestones V1 and V2 correspond to early software versions 0.1.0 and 0.2.0. Releases remain previews until Steam Deck / Android hardware verification is complete.

## [0.3.2] - 2026-10-12

### Fixed

* Private Java is added to the process PATH and JAVA_HOME so Android SDK signing scripts can run it without a system Java installation. Cached private runtimes are configured before tool repair.
* A visible Updates button in the main header opens and scrolls directly to the update controls.
* Setup scrolls vertically on Steam Deck instead of compressing and overlapping Android controls.
* Android and update buttons use two columns with consistent spacing. Keyboard/controller focus scrolls the selected control into view.

### Verification scope

Real Qt layout geometry and focus scrolling are checked at 1280 x 800 and 1000 x 650. Android gameplay is unchanged and remains subject to device testing.

## [0.3.1] - 2026-10-12

### Fixed

* Bundle portable certificate authorities and use verified HTTPS for every preparation-tool, Java and update download. Fix certificate verification failures in frozen Steam Deck builds without disabling TLS checks.
* Validate application installs before replacing an existing app and restore the previous app if the directory swap fails.

### Added

* Setup: Check for updates, download/checksum/compatibility validation, automatic installation and restart with the prior app preserved. Games and saves remain separate.
* Session-only read-only GitHub access for private releases, plus Open releases and Install downloaded update for browser-authenticated downloads without manual extraction.

### Verification scope

HTTPS trust, release selection, credential redirect handling, unsafe archive rejection, checksum failures, update compatibility and installation rollback are tested. Full Android gameplay remains unverified on this build until tested on the Deck.

## [0.3.0] - 2026-10-12

### Added

* Exact-hash adapter for the supplied The Meego v1.32 APK, preserving the native game and preparing a separate Android installation.
* Reviewable bounded native/compiled-resource patches and local service routing through checked ADB reverse communication.
* Reviewed self-authored Meego service integrated into Play/Stop, persistent village saves, reversible backups and portable exports.
* Rules extracted from the user-owned APK into private working data; proprietary APKs/assets are excluded from source and release packages.
* Optional explicit village-save import, preserving an existing launcher save.
* Guided real-Android offline test: guest IPv4/IPv6 restrictions, village/menu observations, building action evidence, save/relaunch and local-service failure/recovery.

### Verification scope

Actual Meego import/preparation/signing, HTTP actions, persistence, backups and exports were exercised locally. Android gameplay was not run here: this environment lacks Binder/Wayland and container privileges. Earlier user-reported Deck gameplay belongs to the earlier Meego release, not this newly signed client. Guided Android checks remain unverified until executed on a compatible guest. Unsupported quests/social behavior and original balance remain incomplete.

## [0.2.0] - 2026-10-12

### Added

* Native Linux launcher with a 1280 × 800 library, local artwork and a new APK Revival logo.
* Add Game → Prepare → Play workflows using the existing V1 engine.
* Touch/mouse/keyboard support and SDL2 controller focus navigation.
* Named background stages, useful errors, guided Waydroid discovery and intended-device selection.
* User-local preparation tools, private Java installation, desktop shortcut installation and Steam instructions.
* Save backup/restore, redacted diagnostics, Advanced evidence views and native portable exports.
* Included self-authored Tap Quest desktop demonstration with persistent progress.
* GitHub release builds, version tags, source archives, SHA-256 checksums and downloadable Linux packages.

### Fixed

* GitHub package startup dependencies: EGL and the full Qt XCB dependency set are installed on the build runner and checked with a real X display.

### Verification scope

The local V2 suite exercised real Qt workflows, actual APK signing, private tool installation and desktop export gameplay/persistence. Android commands are tested at the adapter boundary with doubles. Physical Steam Deck, original Android gameplay, guest networking and physical controller operation remain unverified. No commercial game restoration is claimed. The package targets Linux x86_64, glibc 2.39+.

## [0.1.0] - 2026-10-12

### Added

* V1 Python restoration engine, CLI and legacy Tk workbench.
* Preserved/hash-bound imports, static evidence reports and versioned profiles.
* Explicit signed APK patch operations, local backend and separate rebuild workflows for the self-authored Tap Quest fixture.
* Waydroid runtime adapter, save backups, portable exports and strict offline-verification gates.

### Verification scope

35 local V1 tests passed with actual APK tools and the Tk display enabled. The Android emulator attempt timed out before gameplay checks. This historical release is source-only and does not include the V2 native launcher. Its source remains at the original V1 commit; the historical release tag backfill was blocked by GitHub permissions.

[0.2.0]: https://github.com/onlykappa/Apk-revival/releases/tag/v0.2.0
[0.1.0]: https://github.com/onlykappa/Apk-revival/tree/7458887bf687eaaf8cf29242ba40be518e761abf

[0.3.0]: https://github.com/onlykappa/Apk-revival/releases/tag/v0.3.0

