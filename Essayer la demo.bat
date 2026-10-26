@echo off
cd /d "%~dp0"
if exist "Reliane.exe" (
    start "" "Reliane.exe" --demo --no-tray
) else if exist "dist\Reliane.exe" (
    start "" "dist\Reliane.exe" --demo --no-tray
) else (
    start "" ".venv\Scripts\pythonw.exe" "main.py" --demo --no-tray
)
