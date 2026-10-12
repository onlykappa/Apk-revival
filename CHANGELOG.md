# Version history

Product milestones V1 and V2 correspond to early software versions 0.1.0 and 0.2.0. Releases remain previews until Steam Deck / Android hardware verification is complete.

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

35 local V1 tests passed with actual APK tools and the Tk display enabled. The Android emulator attempt timed out before gameplay checks. This historical release is source-only and does not include the V2 native launcher. Its tag points to the original V1 commit.

[0.2.0]: https://github.com/onlykappa/Apk-revival/releases/tag/v0.2.0
[0.1.0]: https://github.com/onlykappa/Apk-revival/releases/tag/v0.1.0
