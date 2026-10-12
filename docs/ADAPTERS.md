# Game adapters

The engine implements the self-authored `tapquest-v1` fixture and the exact-hash `meego-1.32` local-backend adapter. See [MEEGO.md](MEEGO.md) for real-game scope and evidence. Unknown APKs receive analysis and diagnostics, not fabricated repairs. Imported APKs, supporting JSON, profiles or bundles never install plugins into the workbench.

## Adding a supported game

1. Inspect the original and attach runtime logs, available protocol documentation, recovered local behaviors, assets and save locations. Cite evidence by archive member/DEX string byte offset or local diagnostic artifact.
2. Add a Python adapter in the project's trusted source. Register it in `ADAPTERS`; add an exact package/version or stronger signature recognition in analysis. Do not auto-import code from an APK or profile.
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
