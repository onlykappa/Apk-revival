# Releases and version history

Download the Linux app from [GitHub Releases](https://github.com/onlykappa/Apk-revival/releases). Each version has its own tag, notes, source archive and, from V2 onward, Linux installer package and SHA-256 checksums. The repository is private, so sign in with repository access to download.

* **v0.1.0 / V1 engine**: historical source-only release at the original V1 commit.
* **v0.2.0 / V2 launcher**: initial branded native Linux app preview. Android and physical Steam Deck gameplay remain unverified.

The [changelog](../CHANGELOG.md) records product changes. The app header shows the installed software version. Product milestones V1 and V2 are separate from semantic software versions 0.1.0 and 0.2.0.

## Maintainer release process

1. Update `pyproject.toml` and `apk_revival/__init__.py` to the same new version and add its CHANGELOG section.
2. Push to main. The Release workflow builds the fixture, runs the engine and Qt tests, checks the packaged app with both offscreen and XCB displays, and publishes only after checks pass.
3. Confirm the Release workflow succeeded and the expected files appear in Releases.

An existing published version is never overwritten. Publish a new version for changed binaries. The workflow can also be run from Actions > Release > Run workflow, or by pushing a matching version tag. It uses GitHub's temporary repository token with `contents: write`; no personal token or signing secret is required. Repository policies must allow GitHub Actions and this permission.

Downloads are unsigned application packages. SHA-256 checksums detect corruption and identify exact files; they do not replace a publisher signature. Automatic in-app updating is not implemented. Install a newer package through Setup > Install desktop shortcut to preserve game data and keep a copy of the prior application.
