@echo off
REM Build a standalone BatesPosture app on Windows.
REM Usage: scripts\build_local.bat

setlocal EnableDelayedExpansion
cd /d "%~dp0\.."

echo =^> Installing / syncing dev dependencies...
uv sync --all-groups
if errorlevel 1 ( echo [ERROR] uv sync failed & exit /b 1 )

echo =^> Converting icon.png -^> icon.ico...
uv run python -c ^
  "from PIL import Image; img = Image.open('src/static/icon.png').convert('RGBA'); img.save('src/static/icon.ico', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)]); print('    -> src/static/icon.ico created')"
if errorlevel 1 ( echo [WARNING] Icon conversion failed - using .png fallback )

echo =^> Running PyInstaller...
uv run pyinstaller batesposture.spec --noconfirm
if errorlevel 1 ( echo [ERROR] PyInstaller failed & exit /b 1 )

echo.
echo [OK] Build complete: dist\BatesPosture\
echo.
echo    To create a ZIP:
echo    powershell Compress-Archive -Path dist\BatesPosture\* -DestinationPath BatesPosture-Windows.zip
