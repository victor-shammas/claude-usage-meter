# Releasing Claude Usage Meter

One channel: a **GitHub release** on `victor-shammas/claude-usage-meter` with a notarized DMG for new installs, and a signed Sparkle appcast and zip that installed copies update from. The app is built by `packaging/build_release.sh`.

Installed copies read `releases/latest/download/appcast.xml` (`SUFeedURL` in `packaging/ClaudeUsageMeter.spec`), which always points at the newest release, so **every release must carry its own `appcast.xml`**. The website's download button points at `releases/latest/download/ClaudeUsageMeter.dmg`, so the DMG always has that fixed name.

## What you need

- Homebrew Python 3 (`brew install python`). The app is built arm64-only for macOS 26+, matching that Python.
- A **Developer ID Application** certificate in the login Keychain (team `JPP8RN6BJB`).
- A notarytool Keychain profile. This Mac uses the one made for Quoth: `NOTARY_PROFILE=quoth-notary`.
- **This app's Sparkle private key** in the login Keychain, under the account `claude-usage-meter`. It is separate from Quoth's key. Its public half is `SUPublicEDKey` in the spec. The first time `generate_appcast` uses it, macOS asks for Keychain access; choose **Always Allow**. If the key is ever lost, installed copies can't verify new updates and users must reinstall by hand, so back it up: `.sparkle/2.10.0/bin/generate_keys --account claude-usage-meter -x <file>`.
- `gh`, logged in.

Sparkle 2.10.0 is downloaded into `.sparkle/` (git-ignored) on the first build and checked against a pinned SHA-256.

## Steps

1. **Bump the version.** Set `__version__` in `claude_menubar.py`. Sparkle compares versions, so use numbers and dots only, each release higher than the last.
2. **Update the changelog** in `README.md`.
3. **Build.**
   ```bash
   NOTARY_PROFILE=quoth-notary packaging/build_release.sh
   ```
   It builds and signs the app with Sparkle embedded, notarizes and staples the app, then writes `dist/ClaudeUsageMeter-X.Y.Z.zip` and a signed `dist/appcast.xml`. It also notarizes and staples `dist/ClaudeUsageMeter.dmg`. The run ends with a Gatekeeper check of the app and the DMG.
4. **Commit and push**, then tag: `git tag -a vX.Y.Z -m vX.Y.Z && git push origin main vX.Y.Z`. The appcast's download links point at `releases/download/vX.Y.Z/`, so the tag must match the version.
5. **Publish.**
   ```bash
   gh release create vX.Y.Z -R victor-shammas/claude-usage-meter --verify-tag \
     --title "vX.Y.Z: <headline>" --notes-file <notes.md> \
     dist/ClaudeUsageMeter.dmg dist/ClaudeUsageMeter-X.Y.Z.zip dist/appcast.xml
   ```
6. **Check.** Both https://github.com/victor-shammas/claude-usage-meter/releases/latest/download/appcast.xml and `…/latest/download/ClaudeUsageMeter.dmg` should resolve to the new release. An installed older copy should offer the update from **Check for Updates**.
7. **Update the Apps project board** card "Claude Usage Meter — GitHub release" (Version).

## Website

`docs/` is the GitHub Pages site at https://victorshammas.com/claude-usage-meter/, in the same plain format as Quoth's, Plainview's and Gaugeline's sites: HTML and one stylesheet, with no build step. Pages deploys from `main`, folder `/docs`. After an icon change, run `python3 packaging/make_icon.py`, which rewrites `packaging/AppIcon.icns` and `docs/icon.png`, `favicon.png` and `apple-touch-icon.png`.
