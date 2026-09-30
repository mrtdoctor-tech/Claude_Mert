@echo off
chcp 65001 >nul
rem Yerel Asistan araci: asistani tasimadan onceki ortamina (python-yolu.eski.txt) geri dondurur.
set "DIR=%LOCALAPPDATA%\YerelAsistan"
if not exist "%DIR%\python-yolu.eski.txt" goto none
copy /y "%DIR%\python-yolu.eski.txt" "%DIR%\python-yolu.txt" >nul
echo Asistan eski ortamina dondu:
type "%DIR%\python-yolu.txt"
echo baslat.bat penceresini kapatip yeniden ac.
pause
exit /b 0

:none
echo Geri donulecek bir kayit yok - asistan hic tasinmamis.
pause
exit /b 1
