@echo off
REM ============================================================
REM  Build script for Windows — produces DBFWScanner.exe
REM  Run this from the project root in a venv that has all
REM  dependencies installed (pip install -r requirements.txt)
REM ============================================================

echo Building DBFW Code Scanner for Windows...

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "DBFWScanner" ^
  --hidden-import "google.generativeai" ^
  --hidden-import "google.ai.generativelanguage_v1beta" ^
  --hidden-import "google.auth" ^
  --hidden-import "google.auth.transport.requests" ^
  --hidden-import "PIL._tkinter_finder" ^
  --hidden-import "cv2" ^
  --collect-all "google.generativeai" ^
  main.py

echo.
if exist dist\DBFWScanner.exe (
    echo SUCCESS: dist\DBFWScanner.exe created.
) else (
    echo FAILED: Check the output above for errors.
)
pause
