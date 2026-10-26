@echo off
cd /d "%~dp0"
if exist "Reliane.exe" (
    start "" "Reliane.exe"
) else if exist "dist\Reliane.exe" (
    start "" "dist\Reliane.exe"
) else (
    if exist ".venv\Scripts\pythonw.exe" (
        start "" ".venv\Scripts\pythonw.exe" "main.py"
    ) else (
        echo Compilez l'application avec build.bat ou installez les dependances.
        pause
    )
)
