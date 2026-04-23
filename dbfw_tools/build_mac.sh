#!/bin/bash
# ============================================================
#  Build script for macOS
#  Step 1: PyInstaller → dist/DBFWTools.app
#  Step 2: create-dmg  → DBFWTools.dmg  (drag-to-Applications)
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

# ── Step 1: PyInstaller ───────────────────────────────────────────────────────
echo ""
echo " Step 1/2 — Building app bundle with PyInstaller..."
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
    echo " Check the output above for errors."
    exit 1
fi
echo " PyInstaller succeeded: dist/DBFWTools.app created."

# ── Step 2: DMG (optional) ───────────────────────────────────────────────────
echo ""
echo " Step 2/2 — Building DMG..."
echo ""

if ! command -v create-dmg &>/dev/null; then
    echo " create-dmg not found — skipping DMG build."
    echo " To build the DMG, install create-dmg:"
    echo "   brew install create-dmg"
    echo " Then re-run this script."
    echo ""
    echo " Distributable: dist/DBFWTools.app"
    echo " To share: zip -r DBFWTools_mac.zip dist/DBFWTools.app"
    exit 0
fi

# Copy the uninstaller into dist/ so create-dmg picks it up alongside the app.
cp uninstall_mac.command dist/
chmod +x dist/uninstall_mac.command

# Remove old DMG if it exists
rm -f DBFWTools.dmg

create-dmg \
  --volname "Dragon Ball Fusion World Tools" \
  --volicon "dist/DBFWTools.app/Contents/Resources/icon-windowed.icns" \
  --window-pos 200 120 \
  --window-size 660 460 \
  --icon-size 128 \
  --icon "DBFWTools.app" 180 185 \
  --hide-extension "DBFWTools.app" \
  --app-drop-link 480 185 \
  --icon "uninstall_mac.command" 330 360 \
  --no-internet-enable \
  "DBFWTools.dmg" \
  "dist/" \
  2>/dev/null || \
create-dmg \
  --volname "Dragon Ball Fusion World Tools" \
  --window-pos 200 120 \
  --window-size 660 460 \
  --icon-size 128 \
  --icon "DBFWTools.app" 180 185 \
  --hide-extension "DBFWTools.app" \
  --app-drop-link 480 185 \
  --icon "uninstall_mac.command" 330 360 \
  --no-internet-enable \
  "DBFWTools.dmg" \
  "dist/"

echo ""
if [ -f "DBFWTools.dmg" ]; then
    echo " SUCCESS: DBFWTools.dmg created."
    echo " Share this file with end users."
else
    echo " DMG creation failed. Check the output above."
    echo " Fallback: zip -r DBFWTools_mac.zip dist/DBFWTools.app"
    exit 1
fi
echo ""
