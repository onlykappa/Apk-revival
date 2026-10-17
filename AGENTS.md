# Working on APK Revival

Instructions for every AI assistant on this repository (Codex, Claude and others).
Several assistants work on this project in turn, so the shared log is how each one
knows where the last one stopped.

## Shared log: docs/AI_HANDOFF.md

- **Before you start:** fetch and work from the latest `main`, then read the top
  three entries of `docs/AI_HANDOFF.md`. Newest entries are at the top.
- **Before you finish:** add a new entry at the top with:
  - heading: `## <version> <short title> — <state>` (state: committed, released,
    installed, or pending)
  - date, which assistant you are, and the branch and commit
  - what changed and why, in plain language
  - tests run and their result
  - what was installed on the Steam Deck, if anything
  - what is still unverified or should happen next
- `docs/history/` holds older logs (`OVERNIGHT_HANDOFF.md`,
  `DECK_0.3.19_GITHUB_HANDOFF.md`). Read them for background; do not add entries there.

## Branches, versions and releases

- `main` is the single source of truth. Work on a branch, merge into `main` once
  tests pass, and never leave finished work only on the Deck or on a side branch.
- A version bump changes `pyproject.toml` and `apk_revival/__init__.py` together
  and adds a `CHANGELOG.md` entry containing a `### Verification scope` section that
  mentions Android (the release check requires it).
- Pushing a version change to `main` publishes a GitHub release automatically.
- The in-app Check for updates only offers versions higher than the installed one.
  Do not install a locally built version on the Deck that is numbered higher than
  the latest GitHub release unless it is merged and released, or the app stops
  offering updates.

## Game plugins

- Game-specific support (patches, local servers, mods, extra buttons) lives in a
  plugin package, e.g. `apk_revival/meego/`, registered from its `plugin.py`.
- The core app (everything else under `apk_revival/`) must never import or name a
  plugin. Add an optional hook to `apk_revival/adapters.py`/`plugins.py` instead;
  `tests/test_plugins.py` fails if core code mentions a plugin.
- The public app download and source zip leave plugins out; each release also
  publishes `APK-Revival-plugin-<name>-<version>.zip`, which the app can install.

## Tests

- Run `python -m unittest discover -s tests` (GUI tests also need
  `QT_QPA_PLATFORM=offscreen APKR_V2_UI_TEST=1`).
- GitHub runs the suite on Ubuntu. Tests must not depend on Steam Deck only programs
  or paths such as `waydroid`, `/usr/lib/steamos-waydroid`, `/usr/bin/sudo` or
  `/usr/bin/visudo`; mock or locate them instead.

## Never commit

APKs, OBBs, keystores or signing passwords, saves, logs, caches, tokens, or
anything from `~/.local/share/apk-revival`.
