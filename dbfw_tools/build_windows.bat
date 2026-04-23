@echo off
REM ============================================================
REM  Build script for Windows — produces DBFWTools.exe
REM  Run this from the project root in a venv that has all
REM  dependencies installed (pip install -r requirements.txt)
REM ============================================================

echo Building Dragon Ball Fusion World Tools for Windows...

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "DBFWTools" ^
  --hidden-import "google.genai" ^
  --hidden-import "google.auth" ^
  --hidden-import "google.auth.transport.requests" ^
  --hidden-import "PIL._tkinter_finder" ^
  --hidden-import "pygetwindow" ^
  --hidden-import "pyautogui" ^
  --collect-all "google.genai" ^
  --collect-all "tkinterdnd2" ^
  main.py

echo.
if exist dist\DBFWTools.exe (
    echo SUCCESS: dist\DBFWTools.exe created.
) else (
    echo FAILED: Check the output above for errors.
)
pause
