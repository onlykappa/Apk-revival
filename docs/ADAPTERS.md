# Game adapters

The core app implements only the self-authored `tapquest-v1` fixture. Real games are supported by **game plugins**, such as the exact-hash `meego-1.32` adapter in `apk_revival/meego/` (see [MEEGO.md](MEEGO.md)). Unknown APKs receive analysis and diagnostics, not fabricated repairs. Plugins are installed only by an explicit user action in Setup; imported APKs, supporting JSON, profiles or bundles never install plugin code.

## Adding a supported game

1. Inspect the original and attach runtime logs, available protocol documentation, recovered local behaviors, assets and save locations. Cite evidence by archive member/DEX string byte offset or local diagnostic artifact.
2. Create a plugin package `apk_revival/<name>/` with a `plugin.py` whose `register(add)` calls `add(YourAdapter())`. Name adapters `<name>-<version>`. Recognise the exact game in a `detect` hook (exact hash or stronger signature). Never import the plugin from core code; add an optional hook instead.
3. Implement `plan(store, profile, path)` producing schema 1 JSON with the exact original APK SHA-256, version name/code, selected path, explicit operations, documented assumptions and relevant backend/save configuration.
4. Use exact precondition hashes and review the generated plan and unified diff. V1 operations are `replace_text_file` and `replace_text`. The latter must name an exact match count. Paths must be relative safe archive/decoded paths and supported text extensions.
5. For local backend support, implement real evidence-supported request/response semantics, persistence, errors and lifecycle. Extend backend selection explicitly. Do not return arbitrary success JSON to unknown requests.
6. For rebuild support, produce feasibility first, then a genuinely separate implementation, asset provenance and rebuild progress. Extend export/launcher handling explicitly. Merely selecting a path does not implement it.
7. Add a gameplay verifier which interacts with meaningful mechanics and confirms save/relaunch under network blocking. Generic process-launch success, endpoint redirection and static references never suffice.
8. Add an actual APK/tool integration test and runtime evidence. Document hardware coverage separately from mocks.

## Patch plan contract

```json
{
  "schema_version": 1,
  "adapter": "your-trusted-adapter",
  "apk_sha256": "64 lowercase hex characters",
  "apk_version": {"name": "1.0", "code": "1"},
  "path": "offline_patch",
  "operations": [
    {
      "type": "replace_text",
      "file": "smali/example/Game.smali",
      "expected_sha256": "64 lowercase hex characters of decoded file",
      "old": "exact original text",
      "new": "exact replacement text",
      "count": 1,
      "reason": "evidence-supported local behavior"
    }
  ],
  "assumptions": [],
  "backend": null,
  "save_locations": []
}
```

Generate precondition hashes from a trusted inspection copy. Generic local reviewed plans can use the offline patch engine without adapter code through `prepare GAME offline_patch --plan reviewed.json`. Local-backend and rebuild plans must have an implemented trusted adapter, not just a custom string identifier.

Asset-only changes rebuild the APK archive directly while preserving original compiled resources/DEX and removing old signing entries. Other decoded text changes use apktool. No arbitrary shell operations or native binary patching is accepted. Split APK patch/re-sign support needs a separate implementation which maintains set consistency and signatures; it is not inferred from base APK support.

## Current fixture implementation

Plan generation, config changes, backend semantics and independent rebuild are implemented. Backend source derives directly from the self-authored fixture source. Progress is integer coins and level `1 + coins // 10`. The offline patch uses the preexisting SharedPreferences branch; it does not replace gameplay with a dummy loading screen. The independent rebuild uses the same original mechanics but is clearly a separate desktop game.


## Plugin hooks

All hooks are optional attributes or methods on the registered adapter. The core
calls a hook only if it exists.

| Hook | Used for |
| --- | --- |
| `name`, `supported_paths`, `plan()`, `feasibility()`, `prepare_data()` | Restoration plan and prepared data, as above |
| `detect(profile, zip, finding, endpoints)` | Return True for the exact game; may add findings and endpoints |
| `title`, `controls`, `recommended_path`, `recommendation_reason` | Library title, controls text and analysis recommendation |
| `binary_targets`, `operation_types`, `validate_operation()`, `apply_operation()` | Reviewed binary patches and plugin-specific patch operations |
| `config_path(store, profile)`, `start_backend(data, config, port, apk=, profile=)` | Local game service for Play, exports and portable copies |
| `save_file`, `validate_save(state)` | Progress kept in a host file, for backups and restores |
| `prepared_current(previous, profile)`, `before_play(service, profile, runtime, ctx)` | Client upgrades checked at Prepare and Play |
| `verify_note` | Skip automatic offline verification and explain why |
| `mods`, `mods_dialog(service, game, parent)` | The Mods button and its dialog |
| `game_actions(profile)`, `run_action(service, game, key, ctx)` | Extra Game options buttons |
| `guided_test_dialog(window)` | A guided offline test instead of the automatic one |

Releases publish each plugin as `APK-Revival-plugin-<name>-<version>.zip`
(`plugin.json` plus `apk_revival/<name>/`). The app installs them into its data
folder, `plugins/<name>/`, and keeps them across updates.
