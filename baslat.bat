@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem kurulum.bat writes the path of this computer's Python (Anaconda "asistan" environment or a venv) here.
set "PYFILE=%LOCALAPPDATA%\YerelAsistan\python-yolu.txt"
if not exist "%PYFILE%" goto setup
set /p PYEXE=<"%PYFILE%"
if not exist "%PYEXE%" goto setup
for %%i in ("%PYEXE%") do set "ENVDIR=%%~dpi"
rem Conda environments need their DLL folders on PATH when used without "conda activate".
set "PATH=%ENVDIR%;%ENVDIR%Library\mingw-w64\bin;%ENVDIR%Library\usr\bin;%ENVDIR%Library\bin;%ENVDIR%Scripts;%PATH%"
"%PYEXE%" -c "import ssl" >nul 2>nul
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
