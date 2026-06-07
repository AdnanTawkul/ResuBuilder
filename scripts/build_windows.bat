@echo off
setlocal

echo Building ResuBuilder Windows app...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

python -m PyInstaller ResuBuilder.spec --clean --noconfirm

echo.
echo Build finished.
echo Run: dist\ResuBuilder\ResuBuilder.exe
endlocal
