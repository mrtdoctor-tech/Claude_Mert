@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Yerel Asistan kurulumu ===
echo.

rem Everything computer-specific (Python environment, settings) lives outside the project folder,
rem which may be synced (OneDrive) to another computer where it could not work.
set "HOMEDIR=%LOCALAPPDATA%\YerelAsistan"
set "PYFILE=%HOMEDIR%\python-yolu.txt"
set "VENV=%HOMEDIR%\venv"
if not exist "%HOMEDIR%" mkdir "%HOMEDIR%"

set "VERCHECK=import sys; sys.exit(sys.version_info < (3, 10))"
rem For the python.org route: 3.10+ and not a conda Python (e.g. the copy Pinokio puts on PATH).
set "CHECK=import os, sys; sys.exit(sys.version_info < (3, 10) or os.path.exists(os.path.join(sys.base_prefix, 'conda-meta')))"

rem Old environments inside the project folder came from the first versions (and may be synced from another computer).
if exist .venv (
    echo Proje klasorundeki eski .venv siliniyor, artik kullanilmiyor...
    rmdir /s /q .venv
)

call :findconda
if defined CONDA goto useconda
goto usepython

rem ---------- Anaconda / Miniconda: a separate "asistan" environment ----------
:useconda
echo Anaconda bulundu: %CONDA%
echo [1/3] Anaconda'daki "asistan" ortami hazirlaniyor...
call "%CONDA%" run -n asistan python -c "%VERCHECK%" >nul 2>nul
if not errorlevel 1 goto condaready
echo "asistan" ortami olusturuluyor, birkac dakika surebilir...
call "%CONDA%" create -y -n asistan --override-channels -c conda-forge python=3.12
if errorlevel 1 goto failed
:condaready
call "%CONDA%" run -n asistan python -c "import sys; print(sys.executable)" > "%PYFILE%"
if errorlevel 1 goto failed
goto haveenv

rem ---------- No Anaconda: python.org Python + a venv ----------
:usepython
set "PY="
where py >nul 2>nul
if errorlevel 1 goto trypython
py -3 -c "%CHECK%" >nul 2>nul
if errorlevel 1 goto trypython
set "PY=py -3"
goto havepython
:trypython
where python >nul 2>nul
if errorlevel 1 goto nopython
python -c "%CHECK%" >nul 2>nul
if errorlevel 1 goto nopython
set "PY=python"
:havepython
echo [1/3] Python ortami hazirlaniyor: %VENV%
if not exist "%VENV%\Scripts\python.exe" goto makevenv
"%VENV%\Scripts\python.exe" -c "%CHECK%" >nul 2>nul
if not errorlevel 1 goto venvready
echo Bozuk Python ortami bulundu, siliniyor ve yeniden olusturuluyor...
rmdir /s /q "%VENV%"
:makevenv
%PY% -m venv "%VENV%"
if errorlevel 1 goto failed
:venvready
echo %VENV%\Scripts\python.exe> "%PYFILE%"

rem ---------- Common: install the packages ----------
:haveenv
set /p PYEXE=<"%PYFILE%"
for %%i in ("%PYEXE%") do set "ENVDIR=%%~dpi"
rem Conda environments need their DLL folders on PATH when used without "conda activate".
set "PATH=%ENVDIR%;%ENVDIR%Library\mingw-w64\bin;%ENVDIR%Library\usr\bin;%ENVDIR%Library\bin;%ENVDIR%Scripts;%PATH%"
echo Kullanilan Python: %PYEXE%
"%PYEXE%" -c "import sys; print('  surum', sys.version.split()[0])"
echo.

echo [2/3] Gerekli paketler yukleniyor, bu birkac dakika surebilir...
"%PYEXE%" -m pip install --upgrade pip
"%PYEXE%" -m pip install -r requirements.txt
if errorlevel 1 goto failed
rem NVIDIA graphics card: CUDA libraries so speech recognition can run on the GPU (optional, about 1 GB).
where nvidia-smi >nul 2>nul
if errorlevel 1 goto gpudone
echo NVIDIA ekran karti bulundu, ses tanima icin ekran karti paketleri yukleniyor, yaklasik 1 GB...
"%PYEXE%" -m pip install -r requirements-gpu.txt
if errorlevel 1 echo Ekran karti paketleri kurulamadi, ses tanima islemcide calisacak.
:gpudone
rem Reset the error level: a failed GPU install is not a failed setup.
ver >nul
if errorlevel 1 goto failed

echo [3/3] Yapay zeka modeli indiriliyor, yaklasik 3 GB...
where ollama >nul 2>nul
if errorlevel 1 goto noollama
ollama pull gemma3:4b
if errorlevel 1 goto failed

echo.
echo Kurulum tamamlandi! Asistani baslatmak icin baslat.bat dosyasina cift tikla.
pause
exit /b 0

rem ---------- Helpers and messages ----------
:findconda
set "CONDA="
for %%c in ("%USERPROFILE%\anaconda3" "%LOCALAPPDATA%\anaconda3" "%ProgramData%\anaconda3" "C:\Apps\anaconda3" "C:\anaconda3" "D:\anaconda3" "%USERPROFILE%\miniconda3" "%LOCALAPPDATA%\miniconda3" "%ProgramData%\miniconda3" "C:\Apps\miniconda3" "C:\miniconda3" "D:\miniconda3") do call :considerconda "%%~c"
if defined CONDA goto :eof
rem conda keeps a list of every environment it knows, from all installations; an installation's own folder has Scripts\conda.exe.
if exist "%USERPROFILE%\.conda\environments.txt" for /f "usebackq delims=" %%p in ("%USERPROFILE%\.conda\environments.txt") do call :considerconda "%%p"
if defined CONDA goto :eof
for /f "delims=" %%c in ('where conda 2^>nul') do call :considerconda "%%~dpc.."
goto :eof

:considerconda
rem %1 = a conda installation folder candidate. Pinokio ships its own conda for its apps: never install into it.
if defined CONDA goto :eof
if not exist "%~1\Scripts\conda.exe" goto :eof
echo %~1| findstr /i pinokio >nul && goto :eof
set "CONDA=%~f1\Scripts\conda.exe"
goto :eof

:nopython
echo Ne Anaconda ne de uygun bir Python bulunamadi.
echo.
echo Bu bilgisayarda bulunan Python'lar:
where python 2>nul
py -0p 2>nul
echo.
echo Anaconda'yi ya da https://www.python.org/downloads/ adresinden Python'u kur, sonra bu dosyayi tekrar calistir.
pause
exit /b 1

:noollama
echo Ollama bulunamadi. https://ollama.com/download adresinden Ollama'yi kur,
echo sonra bu dosyayi tekrar calistir.
pause
exit /b 1

:failed
echo.
echo Kurulum sirasinda bir hata olustu. Yukaridaki mesaji kontrol et.
pause
exit /b 1
