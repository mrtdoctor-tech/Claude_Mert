@echo off
chcp 65001 >nul
rem Yerel Asistan araci: "muzik" ortamina OpenAI Whisper ekler, boylece ai_assistant ortamindaki
rem fvts.py ve analiz.py muzik ortaminda calisabilir. Once DENEME yapar: torch/numpy gibi hassas paketlerin
rem surumu degisecekse hicbir sey kurmadan durur (muzik ortamindaki allin1/demucs bozulmasin).
set "ENVPY=C:\Apps\anaconda3\envs\muzik\python.exe"
if not exist "%ENVPY%" goto noenv
set "ENVDIR=C:\Apps\anaconda3\envs\muzik"
set "PATH=%ENVDIR%;%ENVDIR%\Library\mingw-w64\bin;%ENVDIR%\Library\usr\bin;%ENVDIR%\Library\bin;%ENVDIR%\Scripts;%PATH%"

"%ENVPY%" -c "import whisper" >nul 2>nul
if not errorlevel 1 goto already

echo 1/3 Deneme: Whisper kurulursa neler degisir, bakiliyor...
set "PLAN=%TEMP%\whisper_plan.txt"
"%ENVPY%" -m pip install openai-whisper --dry-run > "%PLAN%" 2>&1
if errorlevel 1 goto planfail
findstr /i /c:"Would install" "%PLAN%"
findstr /i /c:"Would install" "%PLAN%" | findstr /i /r "numpy- torch- torchaudio- numba- llvmlite- scipy- librosa-" >nul
if not errorlevel 1 goto risky

echo.
echo 2/3 Hassas paketler degismiyor. Whisper kuruluyor...
"%ENVPY%" -m pip install openai-whisper
if errorlevel 1 goto installfail
goto check

:already
echo Whisper muzik ortaminda zaten kurulu.

:check
echo.
echo 3/3 Kontrol:
"%ENVPY%" -c "import whisper, torch; print('Whisper tamam, torch', torch.__version__, '- ekran karti:', torch.cuda.is_available())"
for /d %%d in ("%USERPROFILE%\My Drive*") do if exist "%%d\HourGlowMusic\Scripts\hg_olcum\muzik_doctor.py" set "DOCTOR=%%d\HourGlowMusic\Scripts\hg_olcum\muzik_doctor.py"
if not defined DOCTOR goto done
echo.
echo muzik_doctor.py ile muzik ortaminin sagligi kontrol ediliyor:
"%ENVPY%" "%DOCTOR%"
:done
echo.
echo Bitti. Bu pencerenin tamamini kopyalayip Claude'a gonder.
pause
exit /b 0

:risky
echo.
echo DURDURULDU: Whisper kurulursa muzik ortamindaki hassas paketlerden biri degisecek (yukaridaki satira bak).
echo Hicbir sey kurulmadi. Bu pencerenin tamamini kopyalayip Claude'a gonder.
pause
exit /b 1

:planfail
echo Deneme yapilamadi:
type "%PLAN%"
pause
exit /b 1

:installfail
echo Kurulum basarisiz oldu. Pencerenin tamamini Claude'a gonder. Gerekirse yedekten geri kurulur.
pause
exit /b 1

:noenv
echo "muzik" ortami bulunamadi: C:\Apps\anaconda3\envs\muzik
pause
exit /b 1
