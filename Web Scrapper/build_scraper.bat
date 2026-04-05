@echo off
REM Pyinstaller build script for scraper.py
echo Building scraper.exe...
pyinstaller --onefile --add-data "config/config.json;config" scraper.py
echo Done. You can find scraper.exe in the dist folder.
pause
