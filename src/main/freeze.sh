#!/bin/bash

set -e

# Go to project root (the folder that contains venv/ and src/)
cd "$(dirname "$0")/../.."

# Clean previous builds
rm -rf build dist LabrollUtility.spec __pycache__

# Activate venv
source venv/bin/activate

# Sanity checks: ensure we are using the venv's python and that PySide6 is importable
python -c "import sys; print('PYTHON:', sys.executable)"
python -c "import PySide6; print('PySide6 OK:', PySide6.__file__)"
python -c "import PyInstaller; print('PyInstaller OK:', PyInstaller.__version__)"

# Build with PyInstaller using the venv interpreter (critical on macOS)
python -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name LabrollUtility \
  --icon assets/icon.icns \
  --collect-all PySide6 \
  --add-data "src/main/python/package/utils/assets:assets" \
  --add-data "src/main/python/package:package" \
  src/main/python/main.py

# Verify output (.app on macOS)
APP_PATH="dist/LabrollUtility.app"
if [ -d "$APP_PATH" ]; then
  echo "Build OK: $APP_PATH"
  open dist
  exit 0
fi

# Fallback: onedir output (folder with executable)
ONEDIR_PATH="dist/LabrollUtility"
if [ -d "$ONEDIR_PATH" ]; then
  echo "Build OK (onedir): $ONEDIR_PATH"
  open dist
  exit 0
fi

echo "ERROR: Build output not found in dist/."
exit 1