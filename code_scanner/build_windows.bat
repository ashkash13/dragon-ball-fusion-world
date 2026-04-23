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
  --hidden-import "google.genai" ^
  --hidden-import "google.auth" ^
  --hidden-import "google.auth.transport.requests" ^
  --hidden-import "PIL._tkinter_finder" ^
  --collect-all "google.genai" ^
  --collect-all "tkinterdnd2" ^
  main.py

echo.
if exist dist\DBFWScanner.exe (
    echo SUCCESS: dist\DBFWScanner.exe created.
) else (
    echo FAILED: Check the output above for errors.
)
pause
