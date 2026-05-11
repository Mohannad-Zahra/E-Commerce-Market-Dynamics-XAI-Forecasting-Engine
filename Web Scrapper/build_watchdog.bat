@echo off
REM Pyinstaller build script for watchdog.py
echo Building watchdog.exe...
pyinstaller --onefile --add-data "config/config.json;config" watchdog.py
echo Done. You can find watchdog.exe in the dist folder.
pause
