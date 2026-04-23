@echo off
setlocal
cd /d "%~dp0"

echo.
echo  Dragon Ball Fusion World Tools
echo  ================================
echo.

REM ── Check Python is installed ─────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python is not installed or not in PATH.
    echo.
    echo  Please install Python 3.11 or newer from:
    echo    https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: During installation, check the box that says
    echo  "Add Python to PATH" before clicking Install Now.
    echo.
    pause
    exit /b 1
)

REM ── Check Python version is 3.11+ ─────────────────────────────────────────
python -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if errorlevel 1 (
    for /f "tokens=*" %%v in ('python --version') do set PYVER=%%v
    echo  ERROR: Python 3.11 or newer is required.
    echo  You have: %PYVER%
    echo.
    echo  Please install a newer version from:
    echo    https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM ── Create venv and install dependencies on first run ─────────────────────
if not exist ".venv\" (
    echo  First run — setting up environment. This takes about a minute...
    echo.
    python -m venv .venv
    if errorlevel 1 (
        echo  ERROR: Could not create virtual environment.
        echo  Try running this script as Administrator, or reinstall Python.
        echo.
        pause
        exit /b 1
    )
    echo  Installing dependencies...
    .venv\Scripts\pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo  ERROR: Failed to install dependencies.
        echo  Check your internet connection and try again.
        echo  To reset, delete the .venv folder and re-run this script.
        echo.
        pause
        exit /b 1
    )
    echo.
    echo  Setup complete!
    echo.
)

REM ── Launch the app ────────────────────────────────────────────────────────
echo  Starting Dragon Ball Fusion World Tools...
echo.
.venv\Scripts\python main.py

endlocal
