@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Same location as in kurulum.bat: this computer's own Python environment, outside the (synced) project folder.
set "PYEXE=%LOCALAPPDATA%\YerelAsistan\venv\Scripts\python.exe"
if not exist "%PYEXE%" goto setup
"%PYEXE%" -c "import sys" >nul 2>nul
if errorlevel 1 goto setup
rem Installs packages added by an update; does nothing (and needs no internet) when all are present.
"%PYEXE%" -m pip install -q --disable-pip-version-check -r requirements.txt
"%PYEXE%" run.py
pause
exit /b 0

:setup
echo Bu bilgisayarda asistan henuz kurulmamis ya da kurulumu bozulmus.
echo Once kurulum.bat dosyasina cift tikla, sonra baslat.bat ile tekrar dene.
pause
exit /b 1
