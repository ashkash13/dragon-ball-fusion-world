@echo off
REM ============================================================
REM  Build script for Windows
REM  Produces: dist\DBFWTools.exe  (self-contained, no install needed)
REM
REM  Run from the dbfw_tools\ directory with the venv active:
REM    .venv\Scripts\activate
REM    build_windows.bat
REM ============================================================

echo.
echo  Building executable with PyInstaller...
echo.

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
if not exist dist\DBFWTools.exe (
    echo  FAILED: PyInstaller did not produce dist\DBFWTools.exe
    echo  Check the output above for errors.
    pause
    exit /b 1
)

echo  SUCCESS: dist\DBFWTools.exe created.
echo  Share this file directly — no installation required.
echo.
pause
