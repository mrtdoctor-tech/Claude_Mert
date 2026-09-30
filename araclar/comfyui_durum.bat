@echo off
chcp 65001 >nul
rem Yerel Asistan araci: ComfyUI'de neyin kurulu oldugunu gosterir (surum, torch/GPU, OpenCV, eklentiler, modeller).
rem HICBIR SEYI DEGISTIRMEZ. Sonuc ayrica Belgeler\comfyui_durum.txt dosyasina yazilir.
set "ENV=C:\Apps\anaconda3\envs\ComfyUI"
set "PY=%ENV%\python.exe"
set "COMFY=P:\Comfy\ComfyUI"
set "OUT=%USERPROFILE%\Documents\comfyui_durum.txt"
if not exist "%PY%" goto noenv
if not exist "%COMFY%\main.py" goto nocomfy
set "PATH=%ENV%;%ENV%\Library\mingw-w64\bin;%ENV%\Library\usr\bin;%ENV%\Library\bin;%ENV%\Scripts;%PATH%"
set "PYTHONIOENCODING=utf-8"
echo ComfyUI inceleniyor, modeller taranirken bir-iki dakika surebilir...
> "%OUT%" echo ===== ComfyUI durum raporu %DATE% %TIME% =====
>> "%OUT%" echo.
>> "%OUT%" echo --- P:\Comfy\ComfyUI.bat
if exist "P:\Comfy\ComfyUI.bat" >> "%OUT%" type "P:\Comfy\ComfyUI.bat"
"%PY%" "%~dp0comfyui_durum.py" "%COMFY%" "P:\pinokio\api" >> "%OUT%" 2>&1
cls
type "%OUT%"
echo.
echo Rapor dosyasi: %OUT%
echo Bu pencerenin tamamini (ya da o dosyayi) Claude'a gonder.
pause
exit /b 0

:noenv
echo ComfyUI conda ortami bulunamadi: %ENV%
pause
exit /b 1

:nocomfy
echo ComfyUI klasoru bulunamadi: %COMFY%
pause
exit /b 1
