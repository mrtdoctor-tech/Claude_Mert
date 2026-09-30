@echo off
chcp 65001 >nul
rem Yerel Asistan araci: asistani "asistan" ortamindan "ai_assistant" ortamina tasir.
rem ai_assistant HourGlow betiklerinin de ortami; once DENEME yapar, onlarin kullandigi paketlerden biri
rem (torch, numpy, whisper...) degisecekse hicbir sey kurmadan durur. Eski "asistan" ortamina dokunmaz.
cd /d "%~dp0.."
set "LOG=%LOCALAPPDATA%\YerelAsistan\tasima_kaydi.txt"
if not exist "%LOCALAPPDATA%\YerelAsistan" mkdir "%LOCALAPPDATA%\YerelAsistan"
>>"%LOG%" echo.
>>"%LOG%" echo ===== %DATE% %TIME% tasima basladi =====
set "TARGET=C:\Apps\anaconda3\envs\ai_assistant"
set "TPY=%TARGET%\python.exe"
if not exist "%TPY%" goto noenv
set "PATH=%TARGET%;%TARGET%\Library\mingw-w64\bin;%TARGET%\Library\usr\bin;%TARGET%\Library\bin;%TARGET%\Scripts;%PATH%"
"%TPY%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto oldpython
"%TPY%" -c "import ssl" >nul 2>nul
if errorlevel 1 goto nossl

echo 1/4 Deneme: asistanin paketleri ai_assistant'a kurulursa neler degisir, bakiliyor...
set "PLAN=%TEMP%\asistan_tasima_plan.txt"
"%TPY%" -m pip install -r requirements.txt --dry-run > "%PLAN%" 2>&1
if errorlevel 1 goto planfail
set "GPU="
where nvidia-smi >nul 2>nul
if not errorlevel 1 set "GPU=1"
if defined GPU "%TPY%" -m pip install -r requirements-gpu.txt --dry-run >> "%PLAN%" 2>&1
findstr /i /c:"Would install" "%PLAN%"
findstr /i /c:"Would install" "%PLAN%" | findstr /i /r "numpy- torch- torchaudio- torchvision- numba- llvmlite- scipy- librosa- soundfile- tiktoken- openai-whisper- transformers- tokenizers- huggingface-hub-" >nul
>>"%LOG%" type "%PLAN%"
if not errorlevel 1 goto risky

echo.
>>"%LOG%" echo 1/4 deneme tamam, hassas paket degismiyor
echo 2/4 HourGlow'un paketleri degismiyor. Asistanin paketleri kuruluyor, birkac dakika surebilir...
"%TPY%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto installfail
if defined GPU "%TPY%" -m pip install --disable-pip-version-check -r requirements-gpu.txt
if errorlevel 1 goto installfail
>>"%LOG%" echo 2/4 paketler kuruldu

echo.
echo 3/4 Kontrol:
"%TPY%" -c "import fastapi, uvicorn, faster_whisper, sherpa_onnx, edge_tts, pypdf, docx, librosa, PIL, pypdfium2; print('Asistan paketleri tamam')"
if errorlevel 1 goto installfail
"%TPY%" -c "import whisper, torch; print('HourGlow tarafi tamam: whisper + torch', torch.__version__)"
if errorlevel 1 echo UYARI: HourGlow tarafinda whisper/torch acilamadi - bu pencereyi Claude'a gonder.

echo.
echo 4/4 Asistan artik ai_assistant ortamini kullanacak.
set "YOL=%LOCALAPPDATA%\YerelAsistan\python-yolu.txt"
rem Geri alma kaydi yalnizca ilk tasimada alinir: araci ikinci kez calistirmak onu bozmasin.
if exist "%YOL%" if not exist "%LOCALAPPDATA%\YerelAsistan\python-yolu.eski.txt" copy /y "%YOL%" "%LOCALAPPDATA%\YerelAsistan\python-yolu.eski.txt" >nul
>"%YOL%" echo %TPY%
>>"%LOG%" echo 4/4 TAMAM: asistan artik %TPY% kullaniyor
echo.
echo Bitti. baslat.bat penceresini kapatip yeniden ac. Sol altta surum ve "GPU" yaziyorsa tamam.
echo Geri donmek istersen: araclar\asistan_ortamini_geri_al.bat
echo Eski "asistan" ortamini birkac gun sorunsuz kullandiktan sonra silebilirsin:
echo   C:\Apps\anaconda3\Scripts\conda.exe env remove -n asistan
pause
exit /b 0

:risky
>>"%LOG%" echo DURDURULDU: hassas bir paket degisecekti, hicbir sey kurulmadi
echo.
echo DURDURULDU: Asistanin paketleri kurulursa HourGlow'un kullandigi paketlerden biri degisecek
echo (yukaridaki "Would install" satirina bak). Hicbir sey kurulmadi, asistan eski ortaminda calismaya devam ediyor.
echo Bu pencerenin tamamini kopyalayip Claude'a gonder.
pause
exit /b 1

:planfail
echo Deneme yapilamadi:
type "%PLAN%"
pause
exit /b 1

:installfail
>>"%LOG%" echo HATA: kurulum ya da kontrol basarisiz, asistan eski ortaminda
echo Kurulum ya da kontrol basarisiz oldu. Asistan hala eski ortamini kullaniyor, bir sey degismedi.
echo Pencerenin tamamini Claude'a gonder.
pause
exit /b 1

:oldpython
echo ai_assistant ortamindaki Python cok eski - asistan en az Python 3.10 ister. Tasima yapilmadi.
pause
exit /b 1

:nossl
echo ai_assistant ortaminda Python'un ssl parcasi acilamiyor. Tasima yapilmadi; pencereyi Claude'a gonder.
pause
exit /b 1

:noenv
echo "ai_assistant" ortami bulunamadi: %TARGET%
pause
exit /b 1
