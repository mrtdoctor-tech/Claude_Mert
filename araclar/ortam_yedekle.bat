@echo off
chcp 65001 >nul
rem Yerel Asistan araci: tum conda ortamlarinin paket listesini yedekler (hicbir seyi degistirmez, silmez).
rem Her ortam icin iki dosya: <ad>.yml (ortami aynen geri kurmak icin) ve <ad>_paketler.txt (okunabilir liste).
set "CONDA=C:\Apps\anaconda3\Scripts\conda.exe"
if not exist "%CONDA%" set "CONDA=%USERPROFILE%\anaconda3\Scripts\conda.exe"
if not exist "%CONDA%" set "CONDA=%USERPROFILE%\miniconda3\Scripts\conda.exe"
if not exist "%CONDA%" goto noconda
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmm"') do set "STAMP=%%d"
set "OUT=%USERPROFILE%\Documents\conda_yedek\%STAMP%"
mkdir "%OUT%" 2>nul
echo Conda ortamlari yedekleniyor, her biri birkac saniye surebilir...
echo Yedek klasoru: %OUT%
echo.
for /f "tokens=1,2" %%a in ('call "%CONDA%" env list ^| findstr /b /v "#"') do call :one "%%a" "%%b"
echo.
echo Bitti. Yedekler bu klasorde: %OUT%
echo Bir ortami geri kurmak gerekirse: conda env create -f "%OUT%\ORTAM_ADI.yml"
explorer "%OUT%"
pause
exit /b 0

:one
rem Ad olmayan satirlar (sadece klasor yolu, ornegin Pinokio'nun conda'si) ve base atlanir.
if "%~2"=="" goto :eof
if /i "%~1"=="base" goto :eof
echo   %~1
"%CONDA%" env export -n %~1 > "%OUT%\%~1.yml" 2>nul
"%CONDA%" list -n %~1 > "%OUT%\%~1_paketler.txt" 2>nul
goto :eof

:noconda
echo Anaconda bulunamadi - C:\Apps\anaconda3 klasoru var mi?
pause
exit /b 1
