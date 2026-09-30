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
rem NVIDIA graphics card: CUDA libraries so speech recognition can run on the GPU.
where nvidia-smi >nul 2>nul
if errorlevel 1 goto run
echo Ekran karti paketleri kontrol ediliyor, ilk seferde yaklasik 1 GB indirilir...
"%PYEXE%" -m pip install -q --disable-pip-version-check -r requirements-gpu.txt
:run
rem 3.42: Ollama may have been quit (e.g. to free the graphics card for ComfyUI); start it again if it is not running.
rem findstr, not find: the conda folders put on PATH above carry a GNU find.exe.
tasklist /fi "imagename eq ollama.exe" 2>nul | findstr /i "ollama.exe" >nul
if not errorlevel 1 goto ollamaok
echo Ollama kapaliydi, baslatiliyor...
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
if not exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" start "Ollama" /min ollama serve
:ollamaok
"%PYEXE%" run.py
pause
exit /b 0

:setup
echo Bu bilgisayarda asistan henuz kurulmamis ya da kurulumu bozulmus.
echo Once kurulum.bat dosyasina cift tikla, sonra baslat.bat ile tekrar dene.
pause
exit /b 1
