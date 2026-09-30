@echo off
chcp 65001 >nul
rem Yerel Asistan araci: asistanin hangi Python ortamini kullandigini ve tasimanin nerede kaldigini gosterir.
set "DIR=%LOCALAPPDATA%\YerelAsistan"
echo Asistanin kullandigi Python:
if exist "%DIR%\python-yolu.txt" type "%DIR%\python-yolu.txt"
if not exist "%DIR%\python-yolu.txt" echo   (kayit yok - kurulum.bat hic calismamis)
echo.
if exist "%DIR%\python-yolu.eski.txt" echo Geri alma kaydi var: tasima en az bir kez sonuna kadar gitti.
if not exist "%DIR%\python-yolu.eski.txt" echo Geri alma kaydi yok: tasima hic tamamlanmadi.
echo.
if exist "%DIR%\tasima_kaydi.txt" echo Tasima kaydi:
if exist "%DIR%\tasima_kaydi.txt" findstr /r /c:"=====" /c:"^[0-9]/4" /c:"DURDURULDU" /c:"HATA" "%DIR%\tasima_kaydi.txt"
echo.
set /p PYEXE=<"%DIR%\python-yolu.txt"
if not exist "%PYEXE%" goto end
echo Asistanin paketleri bu ortamda aciliyor mu:
"%PYEXE%" -c "import fastapi, faster_whisper, sherpa_onnx, pypdf, librosa; print('  evet, tamam')"
:end
echo.
echo Bu pencerenin tamamini kopyalayip Claude'a gonderebilirsin.
pause
