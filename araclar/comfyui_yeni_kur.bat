@echo off
chcp 65001 >nul
rem Yerel Asistan araci: ESKISINE DOKUNMADAN yeni bir ComfyUI kurar (P:\Comfy\ComfyUI_yeni, kendi Python'u ile).
rem Fooocus modellerini kopyalamadan baglar, masaustune "ComfyUI (yeni)" koyar. Tekrar calistirmak guvenli.
set "YOL=%LOCALAPPDATA%\YerelAsistan\python-yolu.txt"
if not exist "%YOL%" goto nopython
set /p PY=<"%YOL%"
for %%I in ("%PY%") do set "ENV=%%~dpI"
set "PATH=%ENV%;%ENV%Library\mingw-w64\bin;%ENV%Library\usr\bin;%ENV%Library\bin;%ENV%Scripts;%PATH%"
set "PYTHONIOENCODING=utf-8"
set "KAYIT=%LOCALAPPDATA%\YerelAsistan\comfyui_kurulum.txt"
echo Yeni ComfyUI kuruluyor. Indirme (yaklasik 2 GB) internet hizina gore 5-30 dakika surebilir.
echo Kayit: %KAYIT%
echo.
"%PY%" -u "%~dp0comfyui_yeni_kur.py" 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath $env:KAYIT"
echo.
echo Bu pencerenin son kismini (ya da %KAYIT% dosyasini) Claude'a gonder.
pause
exit /b 0

:nopython
echo Asistanin Python yolu bulunamadi: %YOL%
pause
exit /b 1
