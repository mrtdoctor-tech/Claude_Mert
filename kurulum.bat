@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Yerel Asistan kurulumu ===
echo.

where python >nul 2>nul
if errorlevel 1 goto nopython

echo [1/3] Python ortami hazirlaniyor...
if not exist .venv python -m venv .venv
if errorlevel 1 goto failed
call .venv\Scripts\activate.bat

echo [2/3] Gerekli paketler yukleniyor, bu birkac dakika surebilir...
python -m pip install --upgrade pip
pip install -r requirements.txt
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
echo Python bulunamadi. https://www.python.org/downloads/ adresinden Python'u kur.
echo Kurarken "Add python.exe to PATH" kutusunu isaretlemeyi unutma, sonra bu dosyayi tekrar calistir.
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
