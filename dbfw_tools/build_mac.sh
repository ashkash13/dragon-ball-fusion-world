#!/bin/bash
# ============================================================
#  Build script for macOS
#  Produces: DBFWTools-Mac.dmg  (drag-to-Applications)
#
#  Run from the dbfw_tools/ directory with the venv active:
#    source .venv/bin/activate
#    bash build_mac.sh
#
#  create-dmg is optional. Install with:
#    brew install create-dmg
#
#  macOS: grant Accessibility permission on first launch:
#  System Settings → Privacy & Security → Accessibility → add app
# ============================================================

set -e

echo ""
echo " Building app bundle with PyInstaller..."
echo ""

pyinstaller \
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
if [ ! -d "dist/DBFWTools.app" ]; then
    echo " FAILED: PyInstaller did not produce dist/DBFWTools.app"
    exit 1
fi
echo " PyInstaller succeeded: dist/DBFWTools.app created."

echo ""
echo " Creating DMG..."
echo ""

if ! command -v create-dmg &>/dev/null; then
    echo " create-dmg not found — skipping DMG."
    echo " Install with: brew install create-dmg"
    echo ""
    echo " Fallback: zip -r DBFWTools-Mac.zip dist/DBFWTools.app"
    exit 0
fi

rm -f DBFWTools-Mac.dmg

create-dmg \
  --volname "Dragon Ball Fusion World Tools" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 128 \
  --icon "DBFWTools.app" 180 185 \
  --hide-extension "DBFWTools.app" \
  --app-drop-link 420 185 \
  --no-internet-enable \
  "DBFWTools-Mac.dmg" \
  "dist/"

echo ""
if [ -f "DBFWTools-Mac.dmg" ]; then
    echo " SUCCESS: DBFWTools-Mac.dmg created."
    echo " Share this file — users open it and drag to Applications."
else
    echo " DMG creation failed."
    echo " Fallback: zip -r DBFWTools-Mac.zip dist/DBFWTools.app"
    exit 1
fi
echo ""
