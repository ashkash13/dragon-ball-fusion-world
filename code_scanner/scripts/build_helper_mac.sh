#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HELPER_DIR="$ROOT/vision_helper"
DIST_DIR="$ROOT/bundled/vision_helper"

python3 -m venv "$HELPER_DIR/.venv"
source "$HELPER_DIR/.venv/bin/activate"
pip install --upgrade pip
pip install -r "$HELPER_DIR/requirements.txt"
pip install pyinstaller

pyinstaller \
  --noconfirm \
  --clean \
  --onefile \
  --name vision_helper \
  "$HELPER_DIR/vision_helper.py"

mkdir -p "$DIST_DIR"
cp "$HELPER_DIR/dist/vision_helper" "$DIST_DIR/vision_helper"

echo "Packaged helper copied to $DIST_DIR"
