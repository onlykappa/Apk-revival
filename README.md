<p align="center">
  <img src="resources/apk-revival-logo.png" alt="APK Revival logo" width="128" />
</p>
<h1 align="center">APK Revival</h1>
<p align="center"><strong>Your mobile games. Back in play.</strong></p>
<p align="center">
  <a href="https://github.com/onlykappa/Apk-revival/releases/latest">Download for Linux</a> ·
  <a href="CHANGELOG.md">What's new</a> ·
  <a href="docs/INSTALL_V2.md">Steam Deck setup</a>
</p>
<p align="center">
  <img src="https://img.shields.io/badge/version-0.7.0-9fe5c4?labelColor=16242b" alt="Version 0.7.0" />
  <img src="https://img.shields.io/badge/Linux-x86__64-9fe5c4?labelColor=16242b" alt="Linux x86_64" />
  <img src="https://img.shields.io/badge/status-preview-efce7d?labelColor=16242b" alt="Preview" />
  <img src="https://img.shields.io/badge/license-MIT-9fe5c4?labelColor=16242b" alt="MIT licence" />
</p>

![The APK Revival library](docs/images/library.png)

APK Revival is a game library for Android games on Linux and Steam Deck. Add an APK, press **Play**, and it installs and opens the game for you. For old games whose online servers have shut down, APK Revival can **prepare** a repaired copy that runs offline, while your original file stays untouched.

## Get started

1. Download `APK-Revival-<version>-linux-x86_64.tar.gz` from [Releases](https://github.com/onlykappa/Apk-revival/releases/latest).
2. Extract it (in Desktop Mode on a Steam Deck) and double-click **APK-Revival**. No Python or terminal is needed.
3. In **Setup**, choose **Install desktop shortcut**. To launch from Gaming Mode, choose **Add to Steam** with Steam closed.

Android games run in [Waydroid](https://waydro.id), which you install once for your system; on a Steam Deck, the [SteamOS Waydroid bundle](https://github.com/pjohno/steamos-waydroid-bundle) is supported. After that, APK Revival starts Android, connects to it and opens your game automatically. It never disables SteamOS protections or installs system packages behind your back. Requires glibc 2.39 or newer.

Want to look around first? **Try desktop demo** plays the included Tap Quest demo without Android.

## What it does

- **Opens any game file.** APK files, and XAPK, APKS and APKM bundles with their split APKs and expansion (OBB) files, from Add game, drag and drop, or your file manager.
- **Plays with one button.** Play installs the game if needed, opens it full screen, and ends the session by itself when you close the game.
- **Keeps your progress safe.** Back up and restore any game's progress from Game options. Restores keep a copy of what they replace.
- **Fits Steam Deck.** Controller, touch and trackpad navigation, a 1280 × 800 layout, and a Steam shortcut for the library or for any single game, with its own icon.
- **Shows what's inside.** Each game's icon, name, version, engine, Android requirement and chip support, read from the APK.
- **Helps with old games.** ARM game support is detected, with a guided setup when it is missing. Each game has a Network setting: log the servers it contacts, answer instantly for dead servers, or block its internet.
- **Repairs offline games.** For supported games, Prepare creates a separate, re-signed copy that works without the original servers, plus any local service it needs. A launch is never presented as proof of offline play: *Imported*, *Prepared*, *Launch tested* and *Verified Offline* are separate states.
- **Updates itself** from GitHub releases, keeping your games and saves.

<details>
<summary>More screenshots</summary>

![Empty library](docs/images/home.png)
![Setup](docs/images/setup.png)
![Game options](docs/images/options.png)
![The Tap Quest demo](docs/images/playing.png)
![Advanced evidence view](docs/images/advanced.png)

</details>

## Game plugins

Repairing a particular game's offline play takes game-specific work, so that work ships as **game plugins** rather than inside the app. A plugin recognises the exact game files it supports and adds what that game needs: patches, a local stand-in for retired servers, extra options or mods.

- The app download contains **no game-specific code and no game files**. You always supply your own APKs.
- Install plugins from **Setup > Game plugins**: download the ones your games need from the matching official release, or install a plugin file. Plugins live with your library data and are kept when the app updates.
- Games that need a missing plugin say so in the library instead of failing.

Plugin authors: see [adapters](docs/ADAPTERS.md). The core app talks to plugins only through optional hooks in `apk_revival/plugins.py` and `apk_revival/adapters.py`.

## Safety and privacy

- Your original APKs are copied into the library read-only and never modified. Repaired copies are separate files.
- Removing a game keeps its saves and backups in a `removed-games` folder; uninstalling from Android always backs up progress first.
- Diagnostics exports leave out game files, saves, signing keys and raw logs, and redact tokens. Everything runs locally, with no account, API key or AI service.

## Status

APK Revival is a preview. Automated tests cover import, preparation, saves, updates and the interface on every change, but behaviour on real Steam Deck hardware is confirmed feature by feature; see the [version history](CHANGELOG.md) for what each release has and has not been verified on.

## For contributors

- [Contributor setup](docs/CONTRIBUTING_V2.md) · [Architecture](docs/ARCHITECTURE_V2.md) · [Verification](docs/VERIFICATION.md) · [Release process](docs/RELEASES.md)
- Several AI assistants work on this project in turn. They follow [AGENTS.md](AGENTS.md) and record each change in the shared log, [docs/AI_HANDOFF.md](docs/AI_HANDOFF.md).
- Controller focus, job stages and launch ownership adapt MIT-licensed patterns from OmniPC. The packaged app includes replaceable Qt libraries; licences and notices are in [resources](resources/THIRD_PARTY_LICENSES.md).
