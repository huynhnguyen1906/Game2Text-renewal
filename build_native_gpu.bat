@echo off
setlocal EnableExtensions

for /f "delims=" %%I in ('powershell -NoProfile -Command "[DateTime]::UtcNow.Ticks"') do set "BUILD_STARTED_TICKS=%%I"

call :build
set "BUILD_EXIT=%ERRORLEVEL%"

powershell -NoProfile -Command "$elapsed = [TimeSpan]::FromTicks([DateTime]::UtcNow.Ticks - [long]$env:BUILD_STARTED_TICKS); Write-Host ('GPU build elapsed: {0:hh\:mm\:ss}' -f $elapsed)"
exit /b %BUILD_EXIT%

:build
set "ROOT=%~dp0"
set "VENV_PYTHON=%ROOT%venv\Scripts\python.exe"
set "ALT_VENV_PYTHON=%ROOT%.venv\Scripts\python.exe"
set "SITE_PACKAGES=%ROOT%venv\Lib\site-packages"
set "ALT_SITE_PACKAGES=%ROOT%.venv\Lib\site-packages"
set "PYTHON=%VENV_PYTHON%"
if not exist "%PYTHON%" set "PYTHON=%ALT_VENV_PYTHON%"
if not exist "%PYTHON%" set "PYTHON=python"
if not exist "%SITE_PACKAGES%" set "SITE_PACKAGES=%ALT_SITE_PACKAGES%"

set "SPEC_FILE=%ROOT%native-game2text-gpu.spec"
set "PACKAGING_DIR=%ROOT%build\packaging-gpu"
set "DIST_APP_DIR=%ROOT%dist\native-game2text-gpu"
set "TEMPLATE_CONFIG=%ROOT%config.template.ini"
set "PACKAGED_CONFIG=%PACKAGING_DIR%\config.ini"
set "PADDLE_RUNTIME_DIR=%ROOT%runtime\paddle"
set "NVIDIA_CU13_BIN=%SITE_PACKAGES%\nvidia\cu13\bin\x86_64"
set "NVIDIA_CUDNN_BIN=%SITE_PACKAGES%\nvidia\cudnn\bin"

if not exist "%SPEC_FILE%" (
  echo Missing GPU spec file: %SPEC_FILE%
  exit /b 1
)

if not exist "%TEMPLATE_CONFIG%" (
  echo Missing starter config template: %TEMPLATE_CONFIG%
  exit /b 1
)

if not exist "%ROOT%resources\bin\win\tesseract" (
  echo Missing bundled Tesseract runtime under resources\bin\win\tesseract
  exit /b 1
)

if not exist "%ROOT%profiles" (
  echo Missing profiles folder: %ROOT%profiles
  exit /b 1
)

if not exist "%PADDLE_RUNTIME_DIR%\official_models" (
  echo Missing Paddle models under %PADDLE_RUNTIME_DIR%\official_models
  echo Run the app with PaddleOCR once to populate runtime\paddle first.
  exit /b 1
)

if not exist "%NVIDIA_CU13_BIN%" (
  echo Missing NVIDIA CUDA cu13 runtime under %NVIDIA_CU13_BIN%
  exit /b 1
)

if not exist "%NVIDIA_CUDNN_BIN%" (
  echo Missing NVIDIA cuDNN runtime under %NVIDIA_CUDNN_BIN%
  exit /b 1
)

if exist "%PACKAGING_DIR%" rmdir /s /q "%PACKAGING_DIR%"
mkdir "%PACKAGING_DIR%" || exit /b 1
copy /y "%TEMPLATE_CONFIG%" "%PACKAGED_CONFIG%" >nul || exit /b 1

"%PYTHON%" -c "from configparser import ConfigParser; from pathlib import Path; p=Path(r'%PACKAGED_CONFIG%'); c=ConfigParser(); c.optionxform=str; c.read(p, encoding='utf-8'); c['OCRCONFIG']['engine']='paddleocr'; c['OCRCONFIG']['paddle_use_gpu']='true'; c['OCRCONFIG']['paddle_gpu_device']='gpu:0'; c['OCRCONFIG']['paddle_runtime_engine']='paddle_dynamic'; c['OCRCONFIG']['paddle_disable_model_source_check']='true'; c['OCRCONFIG']['paddle_cache_dir']=''; c['OCRCONFIG']['paddle_use_doc_orientation_classify']='false'; c['OCRCONFIG']['paddle_use_doc_unwarping']='false'; c['OCRCONFIG']['paddle_use_textline_orientation']='false'; c['OCRCONFIG']['paddle_text_detection_model_name']='PP-OCRv5_mobile_det'; c['OCRCONFIG']['paddle_text_recognition_model_name']=''; open(p,'w',encoding='utf-8').write(''); f=p.open('w', encoding='utf-8'); c.write(f); f.close()"
if errorlevel 1 exit /b 1

pushd "%ROOT%"
"%PYTHON%" -m PyInstaller --noconfirm --clean "%SPEC_FILE%"
set "BUILD_EXIT=%ERRORLEVEL%"
popd

if not "%BUILD_EXIT%"=="0" exit /b %BUILD_EXIT%

if not exist "%DIST_APP_DIR%" (
  echo Build finished but GPU dist folder is missing: %DIST_APP_DIR%
  exit /b 1
)

if not exist "%DIST_APP_DIR%\logs\text" mkdir "%DIST_APP_DIR%\logs\text"
if not exist "%DIST_APP_DIR%\logs\images" mkdir "%DIST_APP_DIR%\logs\images"
copy /y "%ROOT%run_native_admin.bat" "%DIST_APP_DIR%\run_native_admin.bat" >nul

echo GPU build complete: %DIST_APP_DIR%
exit /b 0
