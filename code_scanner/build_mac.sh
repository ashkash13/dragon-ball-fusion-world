#!/bin/bash
# ============================================================
#  Build script for macOS — produces DBFWScanner (binary) and
#  optionally a .app bundle in dist/
#  Run from the project root inside an active venv that has all
#  dependencies installed (pip install -r requirements.txt)
# ============================================================

set -e

echo "Building DBFW Code Scanner for macOS..."

pyinstaller \
  --onefile \
  --windowed \
  --name "DBFWScanner" \
  --hidden-import "google.genai" \
  --hidden-import "google.auth" \
  --hidden-import "google.auth.transport.requests" \
  --hidden-import "PIL._tkinter_finder" \
  --collect-all "google.genai" \
  --collect-all "tkinterdnd2" \
  main.py

echo ""
if [ -f "dist/DBFWScanner" ]; then
    echo "SUCCESS: dist/DBFWScanner created."
    echo "To share: zip -j DBFWScanner_mac.zip dist/DBFWScanner"
else
    echo "FAILED: Check the output above for errors."
    exit 1
fi
