#!/bin/bash
# Double-click this file in Finder to launch Dragon Ball Fusion World Tools.
# On first run it sets up a local Python environment — takes about a minute.

cd "$(dirname "$0")"

echo ""
echo " Dragon Ball Fusion World Tools"
echo " ================================"
echo ""

# ── Check Python 3.11+ is installed ─────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo " ERROR: Python 3 is not installed."
    echo ""
    echo " Please install Python 3.11 or newer from:"
    echo "   https://www.python.org/downloads/"
    echo ""
    echo " Use the python.org installer (not Homebrew) to ensure"
    echo " tkinter is included."
    echo ""
    read -r -p " Press Enter to exit..."
    exit 1
fi

PYVER_OK=$(python3 -c "import sys; print('yes' if sys.version_info >= (3,11) else 'no')" 2>/dev/null)
if [ "$PYVER_OK" != "yes" ]; then
    PYVER_STR=$(python3 --version 2>&1)
    echo " ERROR: Python 3.11 or newer is required."
    echo " You have: $PYVER_STR"
    echo ""
    echo " Please install a newer version from:"
    echo "   https://www.python.org/downloads/"
    echo ""
    read -r -p " Press Enter to exit..."
    exit 1
fi

# ── Create venv and install dependencies on first run ────────────────────────
if [ ! -d ".venv" ]; then
    echo " First run — setting up environment. This takes about a minute..."
    echo ""
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo " ERROR: Could not create virtual environment."
        echo " Try reinstalling Python from python.org and try again."
        echo ""
        read -r -p " Press Enter to exit..."
        exit 1
    fi
    echo " Installing dependencies..."
    .venv/bin/pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo ""
        echo " ERROR: Failed to install dependencies."
        echo " Check your internet connection and try again."
        echo " To reset, delete the .venv folder and re-run this script."
        echo ""
        read -r -p " Press Enter to exit..."
        exit 1
    fi
    echo ""
    echo " Setup complete!"
    echo ""
fi

# ── Launch the app ────────────────────────────────────────────────────────────
echo " Starting Dragon Ball Fusion World Tools..."
echo ""
.venv/bin/python main.py
