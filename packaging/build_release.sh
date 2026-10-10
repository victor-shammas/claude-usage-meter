#!/bin/bash
# Build, sign, notarize and package "Claude Usage Meter.app" for release:
# a DMG for new installs, plus the zip and signed Sparkle appcast that
# installed copies update from. Everything lands in dist/.
#
#   packaging/build_release.sh                 # full signed + notarized release
#   packaging/build_release.sh --no-notarize   # signed local build only
#
# The app targets Apple Silicon on macOS 26+, matching Homebrew's Python
# (which is built arm64-only for the host macOS release).
#
# Prerequisites (one-time):
#   - Homebrew Python 3 (brew install python)
#   - A "Developer ID Application" certificate in the login Keychain.
#   - Notary credentials:  xcrun notarytool store-credentials notary --team-id <TEAMID>
#   - This app's Sparkle private key in the login Keychain, under the account
#     "claude-usage-meter" (Sparkle's generate_keys --account claude-usage-meter).
#     Its public half is SUPublicEDKey in ClaudeUsageMeter.spec.
#
# Overridable via environment: PYTHON, CODESIGN_IDENTITY, NOTARY_PROFILE.
set -euo pipefail

NOTARIZE=1
[[ "${1:-}" == "--no-notarize" ]] && NOTARIZE=0

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
BUILD="$ROOT/build"
DIST="$ROOT/dist"
APP_NAME="Claude Usage Meter"
APP="$DIST/$APP_NAME.app"

PYTHON="${PYTHON:-/opt/homebrew/bin/python3}"
NOTARY_PROFILE="${NOTARY_PROFILE:-notary}"
if [[ -z "${CODESIGN_IDENTITY:-}" ]]; then
    CODESIGN_IDENTITY="$(security find-identity -v -p codesigning \
        | sed -n 's/.*"\(Developer ID Application: .*\)"/\1/p' | head -1)"
fi
[[ -n "$CODESIGN_IDENTITY" ]] || { echo "No Developer ID Application identity found."; exit 1; }
[[ -x "$PYTHON" ]] || { echo "Python not found at $PYTHON"; exit 1; }
export CODESIGN_IDENTITY

VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/claude_menubar.py")"
# A fixed name, so releases/latest/download/ClaudeUsageMeter.dmg (the
# website's and README's download link) always gets the newest version.
DMG="$DIST/ClaudeUsageMeter.dmg"
ZIP="$DIST/ClaudeUsageMeter-$VERSION.zip"
REPO="victor-shammas/claude-usage-meter"

SPARKLE_VERSION="2.10.0"
SPARKLE_SHA256="c2bf58aa8387266ac179357b1415d6f2635f044da8be41042af32425dae6da0c"
SPARKLE="$ROOT/.sparkle/$SPARKLE_VERSION"
SPARKLE_KEY_ACCOUNT="claude-usage-meter"

echo "==> Claude Usage Meter $VERSION"
echo "    Python:   $PYTHON ($("$PYTHON" --version))"
echo "    Identity: $CODESIGN_IDENTITY"

if [[ ! -d "$SPARKLE/Sparkle.framework" ]]; then
    echo "==> Fetching Sparkle $SPARKLE_VERSION"
    mkdir -p "$SPARKLE"
    curl -fsSL -o "$SPARKLE/sparkle.tar.xz" \
        "https://github.com/sparkle-project/Sparkle/releases/download/$SPARKLE_VERSION/Sparkle-$SPARKLE_VERSION.tar.xz"
    echo "$SPARKLE_SHA256  $SPARKLE/sparkle.tar.xz" | shasum -a 256 -c -
    tar -xJf "$SPARKLE/sparkle.tar.xz" -C "$SPARKLE"
    rm "$SPARKLE/sparkle.tar.xz"
fi

echo "==> Preparing build venv"
rm -rf "$BUILD" "$DIST"
"$PYTHON" -m venv "$BUILD/venv"
"$BUILD/venv/bin/pip" install --quiet --upgrade pip
"$BUILD/venv/bin/pip" install --quiet -r "$ROOT/requirements.txt" \
    pyobjc-framework-ServiceManagement pyinstaller

echo "==> Building app (PyInstaller signs every binary with the hardened runtime)"
"$BUILD/venv/bin/pyinstaller" --noconfirm --clean \
    --workpath "$BUILD/pyinstaller" --distpath "$DIST" "$HERE/ClaudeUsageMeter.spec"

echo "==> Embedding Sparkle"
FW="$APP/Contents/Frameworks/Sparkle.framework"
ditto "$SPARKLE/Sparkle.framework" "$FW"
# The XPC services are only for sandboxed apps; this one isn't sandboxed.
rm -rf "$FW/Versions/B/XPCServices" "$FW/XPCServices"
# Sign inside-out with the hardened runtime, as Sparkle's docs prescribe.
for item in "$FW/Versions/B/Autoupdate" "$FW/Versions/B/Updater.app" "$FW"; do
    codesign --force --timestamp --options runtime --sign "$CODESIGN_IDENTITY" "$item"
done

# Re-sign the outer bundle so its seal covers the final Info.plist/resources.
codesign --force --timestamp --options runtime \
    --entitlements "$HERE/entitlements.plist" \
    --sign "$CODESIGN_IDENTITY" "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"
lipo -archs "$APP/Contents/MacOS/$APP_NAME"

notarize() {
    xcrun notarytool submit "$1" --keychain-profile "$NOTARY_PROFILE" --wait
}

if (( NOTARIZE )); then
    echo "==> Notarizing app"
    ditto -c -k --keepParent "$APP" "$BUILD/app.zip"
    notarize "$BUILD/app.zip"
    xcrun stapler staple "$APP"
fi

echo "==> Building update zip and appcast"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"
FEED="$BUILD/feed"
mkdir -p "$FEED"
cp "$ZIP" "$FEED/"
"$SPARKLE/bin/generate_appcast" "$FEED" --account "$SPARKLE_KEY_ACCOUNT" \
    --download-url-prefix "https://github.com/$REPO/releases/download/v$VERSION/"
grep -q 'sparkle:edSignature' "$FEED/appcast.xml" \
    || { echo "The appcast isn't signed: is the Sparkle key in this Keychain?"; exit 1; }
cp "$FEED/appcast.xml" "$DIST/appcast.xml"

echo "==> Building DMG"
STAGE="$BUILD/dmg"
mkdir -p "$STAGE"
ditto "$APP" "$STAGE/$APP_NAME.app"
ln -s /Applications "$STAGE/Applications"
hdiutil create -quiet -volname "$APP_NAME" -srcfolder "$STAGE" \
    -fs HFS+ -format UDZO -ov "$DMG"
codesign --force --timestamp --sign "$CODESIGN_IDENTITY" "$DMG"

if (( NOTARIZE )); then
    echo "==> Notarizing DMG"
    notarize "$DMG"
    xcrun stapler staple "$DMG"
    echo "==> Gatekeeper assessment"
    spctl --assess --type execute --verbose=2 "$APP"
    spctl --assess --type open --context context:primary-signature --verbose=2 "$DMG"
fi

echo "==> Done. Release assets in $DIST:"
ls -1 "$DIST" | grep -v '\.app$'
