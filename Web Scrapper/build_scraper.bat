@echo off
REM Pyinstaller build script for scraper.py
echo Building scraper.exe...
pyinstaller --onefile --collect-all playwright --collect-submodules payload --add-data "config/config.json;config" --add-data "payload;payload" --hidden-import playwright.async_api scraper.py
echo Done. You can find scraper.exe in the dist folder.
pause
