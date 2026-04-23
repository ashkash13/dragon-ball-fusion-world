@echo off
REM ============================================================
REM  Build script for Windows — produces DBFWRedeemer.exe
REM  Run from the code_redeemer/ directory inside an active venv
REM  that has all dependencies installed:
REM    pip install -r requirements.txt
REM ============================================================

echo Building DBFW Code Redeemer for Windows...

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "DBFWRedeemer" ^
  --hidden-import "pygetwindow" ^
  --hidden-import "PIL._tkinter_finder" ^
  --hidden-import "cv2" ^
  main.py

echo.
if exist dist\DBFWRedeemer.exe (
    echo SUCCESS: dist\DBFWRedeemer.exe created.
) else (
    echo FAILED: Check the output above for errors.
)
pause
