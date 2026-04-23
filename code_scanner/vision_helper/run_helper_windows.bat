@echo off
set SCRIPT_DIR=%~dp0
call "%SCRIPT_DIR%\.venv\Scripts\activate.bat"
python "%SCRIPT_DIR%\vision_helper.py" %*
