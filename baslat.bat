@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Once kurulum.bat dosyasini calistir.
    pause
    exit /b 1
)
rem Installs packages added by an update; does nothing (and needs no internet) when all are present.
.venv\Scripts\python.exe -m pip install -q --disable-pip-version-check -r requirements.txt
.venv\Scripts\python.exe run.py
pause
