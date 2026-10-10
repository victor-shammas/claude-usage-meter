# PyInstaller spec for "Claude Usage Meter.app". Built by build_release.sh;
# signing identity and entitlements arrive via environment variables.
import os
import re
from pathlib import Path

HERE = Path(SPECPATH)
SCRIPT = HERE.parent / "claude_menubar.py"
VERSION = re.search(r'^__version__ = "([^"]+)"', SCRIPT.read_text(), re.M).group(1)
APP_NAME = "Claude Usage Meter"

a = Analysis(
    [str(SCRIPT)],
    hiddenimports=["ServiceManagement"],
    excludes=["tkinter", "unittest", "pydoc", "test"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    target_arch="arm64",
    codesign_identity=os.environ.get("CODESIGN_IDENTITY"),
    entitlements_file=str(HERE / "entitlements.plist"),
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME)
app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon=str(HERE / "AppIcon.icns"),
    bundle_identifier="io.github.victor-shammas.claude-usage-meter",
    version=VERSION,
    info_plist={
        "CFBundleDisplayName": APP_NAME,
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "26.0",
        "LSUIElement": True,  # menu bar only: no Dock icon, no app menu
        "LSApplicationCategoryType": "public.app-category.developer-tools",
        "NSHumanReadableCopyright": "MIT License · Victor Shammas",
    },
)
