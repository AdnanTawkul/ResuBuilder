$ErrorActionPreference = "Stop"

Write-Host "Building ResuBuilder Windows app..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist) { Remove-Item dist -Recurse -Force }

python -m PyInstaller ResuBuilder.spec --clean --noconfirm

Write-Host "Build finished." -ForegroundColor Green
Write-Host "Run: dist\ResuBuilder\ResuBuilder.exe" -ForegroundColor Yellow
