# -*- mode: python ; coding: utf-8 -*-

# LabrollUtility.spec
# Python 3.10 / PySide6 / macOS Apple Silicon (arm64)

import plistlib
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.building.osx import BUNDLE


# --------------------------------------------------
# Version (source unique : version.plist)
# --------------------------------------------------

def read_version(plist_path: str) -> str:
    p = Path(plist_path)
    if not p.exists():
        return "0.0.0"
    with p.open("rb") as f:
        data = plistlib.load(f)
    return str(data.get("CFBundleShortVersionString", "0.0.0"))


VERSION = read_version("version.plist")


# --------------------------------------------------
# PySide6 hidden imports
# --------------------------------------------------

hiddenimports = collect_submodules("PySide6")


# --------------------------------------------------
# Paths
# --------------------------------------------------

MAIN_SCRIPT = "python/main.py"
PATHEX = ["python"]

DATAS = [
    ("python/package/utils/assets", "assets"),
]


# --------------------------------------------------
# Analysis
# --------------------------------------------------

a = Analysis(
    [MAIN_SCRIPT],
    pathex=PATHEX,
    binaries=[],
    datas=DATAS,
    hiddenimports=hiddenimports,
    excludes=["fbs", "fbs_runtime"],
    noarchive=False,
)


# --------------------------------------------------
# PYZ
# --------------------------------------------------

pyz = PYZ(a.pure)


# --------------------------------------------------
# Executable
# --------------------------------------------------

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LabrollUtility",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch="arm64",
)


# --------------------------------------------------
# Collect
# --------------------------------------------------

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="LabrollUtility",
)


# --------------------------------------------------
# macOS App Bundle
# --------------------------------------------------

app = BUNDLE(
    coll,
    name="LabrollUtility.app",
    icon="python/package/utils/assets/icon.icns",
    bundle_identifier="com.be4post.labrollutility",
    info_plist={
        "CFBundleName": "LabrollUtility",
        "CFBundleDisplayName": "LabrollUtility",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
    },
)