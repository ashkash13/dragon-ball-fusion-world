$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$helperDir = Join-Path $root "vision_helper"
$distDir = Join-Path $root "bundled\vision_helper"

python -m venv "$helperDir\.venv"
& "$helperDir\.venv\Scripts\Activate.ps1"
pip install --upgrade pip
pip install -r "$helperDir\requirements.txt"
pip install pyinstaller

pyinstaller `
  --noconfirm `
  --clean `
  --onefile `
  --name vision_helper `
  "$helperDir\vision_helper.py"

New-Item -ItemType Directory -Force -Path $distDir | Out-Null
Copy-Item "$helperDir\dist\vision_helper.exe" "$distDir\vision_helper.exe" -Force

Write-Host "Packaged helper copied to $distDir"
