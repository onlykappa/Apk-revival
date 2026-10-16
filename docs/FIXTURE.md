# Tap Quest fixture

A self-authored executable Android game with no proprietary assets or dependencies. Java source, Android manifest and config are under `fixtures/android/`. The original client intentionally selects remote mode and points to `https://retired.tapquest.invalid`, an unavailable example domain. This makes the absence of server-backed progression visible without contacting a real service.

Meaningful gameplay: a visible Collect coin button increments coins; every ten coins raises the level. Local-mode progress is committed to `SharedPreferences` (`tapquest.xml`). Remote mode reads/persists progression through a small source-documented protocol.

| Endpoint | Request | Response / behavior |
|---|---|---|
| `GET /health` | No body | Backend identity and fresh per-start token; probe only |
| `GET /state` | No body | `{"coins": 0, "level": 1}` or persisted state |
| `POST /action` | Exactly `{"action":"collect"}` | Increment one coin, persist atomically, return resulting state |
| Other paths/actions | Any | 404/400; no invented authentication, purchases or multiplayer |

The offline patch changes only `assets/revival.json` to select existing local behavior. The local backend path changes that same config to point to guest loopback, reached through verified ADB reverse forwarding. Java gameplay code and compiled resources are preserved in these fixture operations.

The independent desktop rebuild has separately written Tk gameplay, uses the same coin/level mechanics and stores its own JSON save. It needs no Android runtime and is never labeled as restoration of the original APK.

## Reproduce

```bash
python3 scripts/bootstrap_tools.py --fixture
source "$HOME/.cache/apk-revival/tools/env.sh"
python3 scripts/build_fixture.py \
  --android-jar "$HOME/.cache/apk-revival/tools/android-35/android.jar" \
  --ecj "$HOME/.cache/apk-revival/tools/ecj.jar"
python3 scripts/demo.py
```

`build/demo-exports/` contains all three portable packages and a precise demonstration report. `build/demo-data/` is private ignored test work; never commit it. Each rebuilt artifact is actually signed and checked with Android `apksigner`, not renamed from a plain ZIP. The build script uses ephemeral fixture signing keys; the workbench maintains a private local signing identity for restoration exports.

To test Android gameplay, configure a running Waydroid guest in the workbench, prepare a path, and run Verify. To exercise the independent rebuild, prepare that path and press Play, or run its exported `run.py`. The built APK and test exports supplied in a release are self-authored fixtures only.

