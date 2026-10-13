# Releases and version history

Download the Linux app from [GitHub Releases](https://github.com/onlykappa/Apk-revival/releases). Published versions have a tag, notes, source archive, Linux installer package and SHA-256 checksums. The repository is private, so sign in with repository access to download.

* **V1 engine / software 0.1.0**: historical source milestone at [the original V1 commit](https://github.com/onlykappa/Apk-revival/tree/7458887bf687eaaf8cf29242ba40be518e761abf). A separate v0.1.0 GitHub release tag was not published.
* **v0.3.7 / One-click SteamOS Android startup**: starts the existing persistent Android image from Play when needed, reconnects ADB, and avoids re-preparation. Steam Deck runtime verification is still required.\n* **v0.3.6 / SteamOS Konsole startup fix**: cleans inherited packaged Qt plugin settings when launching host Konsole for Waydroid container authorization.
* **v0.3.5 / SteamOS library isolation**: fixes the `OPENSSL_3.4.0 not found` error when running Waydroid/systemctl through an updated packaged launcher. No game data is changed.
* **v0.3.4 / Prepare once, Play anytime**: streamlined primary game actions, reused prepared artifacts after restart, automatic Android connection at Play, and explicit preparation repair. Physical Waydroid gameplay remains device-dependent.
* **v0.3.0 / Meego adapter**: original-game preparation and a guided Android test, with no inherited offline verification claim.
* **v0.2.0 / V2 launcher**: initial branded native Linux app preview. Android and physical Steam Deck gameplay remain unverified.

The [changelog](../CHANGELOG.md) records product changes. The app header shows the installed software version. Product milestones V1 and V2 are separate from semantic software versions 0.1.0 and 0.2.0.

## Maintainer release process

1. Update `pyproject.toml` and `apk_revival/__init__.py` to the same new version and add its CHANGELOG section.
2. Push to main. The Release workflow builds the fixture, runs the engine and Qt tests, checks the packaged app with both offscreen and XCB displays, and publishes only after checks pass.
3. Confirm the Release workflow succeeded and the expected files appear in Releases.

An existing published version is never overwritten. Publish a new version for changed binaries. The workflow can also be run from Actions > Release > Run workflow, or by pushing a matching version tag. It uses GitHub's temporary repository token with `contents: write`; no personal token or signing secret is required. Repository policies must allow GitHub Actions and this permission.

Downloads are unsigned application packages. SHA-256 checksums detect corruption and identify exact files; they do not replace a publisher signature. Automatic in-app updating is not implemented. Install a newer package through Setup > Install desktop shortcut to preserve game data and keep a copy of the prior application.

## Historical V1 tag

The historical V1 release backfill returned HTTP 403 because GitHub Actions cannot tag an older commit whose workflow files differ from the default branch with its default token. This does not affect current release downloads. V1 history remains in CHANGELOG and the original commit. Backfilling that tag requires a repository owner using GitHub or a separately authorized maintainer tool. Never move the V1 tag to V2 code to avoid this restriction.
