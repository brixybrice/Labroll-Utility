#!/bin/bash
set -e

# Aller à la racine du projet
cd "$(dirname "$0")/../.."
ROOT_DIR="$(pwd)"
VERSION_PLIST="${ROOT_DIR}/version.plist"
echo VERSION_PLIST

# Nettoyage
rm -rf build dist *.spec __pycache__

# Activer le venv
source venv/bin/activate

# Sanity checks
python -c "import sys; print('PYTHON:', sys.executable)"
python -c "import PySide6; print('PySide6 OK')"
python -c "import PyInstaller; print('PyInstaller OK')"

# Build PyInstaller
pyinstaller src/main/LabrollUtility.spec --clean

APP_NAME="LabrollUtility"

# Lire automatiquement la version depuis version.plist (CFBundleShortVersionString)

if [ ! -f "$VERSION_PLIST" ]; then
  echo "ERROR: version.plist not found at $VERSION_PLIST"
  exit 1
fi

VERSION=$(python - <<PY
import plistlib
from pathlib import Path

p = Path("${VERSION_PLIST}")
with p.open("rb") as f:
    data = plistlib.load(f)

print(data.get("CFBundleShortVersionString", "0.0.0"))
PY
)

echo "[FREEZE] Version from version.plist = ${VERSION}"

APP_PATH="dist/${APP_NAME}.app"
DMG_NAME="dist/${APP_NAME}-${VERSION}.dmg"

if [ ! -d "$APP_PATH" ]; then
  echo "ERROR: App not found at $APP_PATH"
  exit 1
fi

# Nettoyage ancien DMG
rm -f "$DMG_NAME"

# Création du DMG
create-dmg \
  --volname "${APP_NAME}" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 120 \
  --icon "${APP_NAME}.app" 150 200 \
  --app-drop-link 450 200 \
  "$DMG_NAME" \
  "dist"

echo "Build OK:"
echo " - App : $APP_PATH"
echo " - DMG : $DMG_NAME"

open dist