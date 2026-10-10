#!/bin/bash
# Build, sign, notarize and package "Claude Usage Meter.app" into a DMG.
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
DMG="$DIST/ClaudeUsageMeter-$VERSION.dmg"

echo "==> Claude Usage Meter $VERSION"
echo "    Python:   $PYTHON ($("$PYTHON" --version))"
echo "    Identity: $CODESIGN_IDENTITY"

echo "==> Preparing build venv"
rm -rf "$BUILD" "$DIST"
"$PYTHON" -m venv "$BUILD/venv"
"$BUILD/venv/bin/pip" install --quiet --upgrade pip
"$BUILD/venv/bin/pip" install --quiet -r "$ROOT/requirements.txt" \
    pyobjc-framework-ServiceManagement pyinstaller

echo "==> Building app (PyInstaller signs every binary with the hardened runtime)"
"$BUILD/venv/bin/pyinstaller" --noconfirm --clean \
    --workpath "$BUILD/pyinstaller" --distpath "$DIST" "$HERE/ClaudeUsageMeter.spec"

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

shasum -a 256 "$DMG"
echo "==> Done: $DMG"
