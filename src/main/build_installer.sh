#!/bin/bash

# Freeze script for LabrollUtility

APP_NAME="Labroll Utility"
SCRIPT="python/main.py"
DIST_PATH="dist"
BUILD_PATH="build"

# Clean previous builds
rm -rf "$DIST_PATH" "$BUILD_PATH"

pyinstaller \
  --name "$APP_NAME" \
  --windowed \
  --onefile \
  --version-file version.plist \
  "$SCRIPT"