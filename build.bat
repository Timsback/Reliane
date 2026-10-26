@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 exit /b 1
)
.venv\Scripts\python -m pip install -r requirements-lock.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python fetch_assets.py
if errorlevel 1 exit /b 1
.venv\Scripts\python -m unittest discover -s tests -v
if errorlevel 1 exit /b 1
.venv\Scripts\python build_release.py
if errorlevel 1 exit /b 1
echo.
echo Reliane est pret : %~dp0dist\Reliane.exe
echo Vos fichiers settings.json et MyDosoft.exe sont conserves.
endlocal
