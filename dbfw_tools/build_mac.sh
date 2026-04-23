#!/bin/bash
# ============================================================
#  Build script for macOS — produces DBFWTools (binary)
#  Run from the project root inside an active venv that has all
#  dependencies installed (pip install -r requirements.txt)
#
#  macOS: grant Accessibility permission on first launch:
#  System Settings → Privacy & Security → Accessibility → add app
# ============================================================

set -e

echo "Building Dragon Ball Fusion World Tools for macOS..."

pyinstaller \
  --onefile \
  --windowed \
  --name "DBFWTools" \
  --hidden-import "google.genai" \
  --hidden-import "google.auth" \
  --hidden-import "google.auth.transport.requests" \
  --hidden-import "PIL._tkinter_finder" \
  --hidden-import "pygetwindow" \
  --hidden-import "pyautogui" \
  --collect-all "google.genai" \
  --collect-all "tkinterdnd2" \
  main.py

echo ""
if [ -f "dist/DBFWTools" ]; then
    echo "SUCCESS: dist/DBFWTools created."
    echo "To share: zip -j DBFWTools_mac.zip dist/DBFWTools"
else
    echo "FAILED: Check the output above for errors."
    exit 1
fi
