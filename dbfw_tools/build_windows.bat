@echo off
REM ============================================================
REM  Build script for Windows
REM  Step 1: PyInstaller → dist\DBFWTools.exe
REM  Step 2: Inno Setup  → installer_output\DBFWTools_Setup.exe
REM
REM  Run from the dbfw_tools\ directory with the venv active:
REM    .venv\Scripts\activate
REM    build_windows.bat
REM
REM  Inno Setup 6 is optional. If installed, the full installer
REM  wizard is built automatically after PyInstaller.
REM  Download from: https://jrsoftware.org/isinfo.php
REM ============================================================

echo.
echo  Step 1/2 — Building executable with PyInstaller...
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
echo  PyInstaller succeeded: dist\DBFWTools.exe created.

REM ── Step 2: Inno Setup installer (optional) ───────────────────────────────
echo.
echo  Step 2/2 — Building installer wizard with Inno Setup...
echo.

set "ISCC="
set "PFx86=%ProgramFiles(x86)%"
if exist "%PFx86%\Inno Setup 6\ISCC.exe" set "ISCC=%PFx86%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
    echo  Inno Setup not found — skipping installer build.
    echo  To build the installer wizard, install Inno Setup 6 from:
    echo    https://jrsoftware.org/isinfo.php
    echo  Then re-run this script.
    echo.
    echo  Distributable: dist\DBFWTools.exe
    goto :done
)

"%ISCC%" installer_windows.iss
echo.
if exist installer_output\DBFWTools_Setup.exe (
    echo  SUCCESS: installer_output\DBFWTools_Setup.exe created.
    echo  Share this file with end users.
) else (
    echo  Inno Setup compilation failed. Check the output above.
)

:done

echo.
pause
