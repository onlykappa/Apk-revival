# Publish source to the supplied repository

Target: https://github.com/onlykappa/Apk-revival

If ChatGPT's GitHub connector returns 404, reconnect the GitHub plugin using the account which owns this repository and review its requested repository access. If authorization offers repository selection, select Apk-revival and save. For a GitHub App installation, add the repository on its configuration page. A connected profile alone does not prove repository read/write access. No credentials belong in source files or this archive.

Otherwise use Git locally after extracting the source ZIP. The archive includes source files and a separate `demo/` directory. Demo APK/ZIP artifacts are for local testing and not staged by the following source-only commit:

```bash
cd Apk-revival
git init -b main
git remote add origin https://github.com/onlykappa/Apk-revival.git
git add apk_revival tests scripts docs fixtures examples .github README.md LICENSE pyproject.toml .gitignore
git diff --cached --stat
git commit -m "Build APK Revival V1 restoration workbench"
git fetch origin
```

If the remote is empty:

```bash
git push -u origin main
```

If you created it with an initial README/license, preserve that commit:

```bash
git merge origin/main --allow-unrelated-histories
# Resolve any README/LICENSE conflicts by retaining the complete V1 source documentation.
git add README.md LICENSE
git commit  # only if Git requests a merge commit
git push -u origin main
```

Authenticate using your normal Git credential manager or GitHub CLI; do not paste a token into a URL or source file. Never force-push over unrelated history. Review staged contents for imported games, private saves, logs and signing secrets. Workbench data defaults outside the repository and is not part of this commit.

An optional self-authored fixture APK may be uploaded as a release artifact. Proprietary user inputs must not be uploaded automatically.

