#!/bin/bash
# ============================================================
#  Build script for macOS — produces DBFWRedeemer binary
#  Run from the code_redeemer/ directory inside an active venv
#  that has all dependencies installed:
#    pip install -r requirements.txt
#
#  macOS note: the built app needs Accessibility permission the
#  first time it runs (System Preferences → Security & Privacy
#  → Accessibility).  Add the app or terminal there if prompted.
# ============================================================

set -e

echo "Building DBFW Code Redeemer for macOS..."

pyinstaller \
  --onefile \
  --windowed \
  --name "DBFWRedeemer" \
  --hidden-import "pygetwindow" \
  --hidden-import "PIL._tkinter_finder" \
  --hidden-import "cv2" \
  main.py

echo ""
if [ -f "dist/DBFWRedeemer" ]; then
    echo "SUCCESS: dist/DBFWRedeemer created."
    echo "To share: zip -j DBFWRedeemer_mac.zip dist/DBFWRedeemer"
else
    echo "FAILED: Check the output above for errors."
    exit 1
fi
