@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Yerel Asistan kurulumu ===
echo.

rem A usable Python is 3.10+ and not a conda/miniconda one (e.g. the copy Pinokio puts on PATH).
set "CHECK=import os, sys; sys.exit(sys.version_info < (3, 10) or os.path.exists(os.path.join(sys.base_prefix, 'conda-meta')))"

rem Prefer the "py" launcher that comes with the python.org installer.
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
echo Kullanilan Python:
%PY% -c "import sys; print('  ', sys.executable, sys.version.split()[0])"
echo.

echo [1/3] Python ortami hazirlaniyor...
if not exist .venv\Scripts\python.exe goto makevenv
.venv\Scripts\python.exe -c "%CHECK%" >nul 2>nul
if not errorlevel 1 goto venvready
echo Eski veya bozuk .venv klasoru bulundu, siliniyor ve yeniden olusturuluyor...
rmdir /s /q .venv
:makevenv
%PY% -m venv .venv
if errorlevel 1 goto failed
:venvready

echo [2/3] Gerekli paketler yukleniyor, bu birkac dakika surebilir...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
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

:nopython
echo Uygun bir Python bulunamadi.
echo https://www.python.org/downloads/ adresinden Python'u kur.
echo Kurarken "Add python.exe to PATH" kutusunu isaretlemeyi unutma, sonra bu dosyayi tekrar calistir.
echo Not: Pinokio veya Anaconda/Miniconda ile gelen Python bilerek kullanilmiyor.
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
