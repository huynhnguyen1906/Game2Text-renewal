@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "VENV_PYTHON=%ROOT%venv\Scripts\python.exe"
set "ALT_VENV_PYTHON=%ROOT%.venv\Scripts\python.exe"
set "PYTHON=%VENV_PYTHON%"
if not exist "%PYTHON%" set "PYTHON=%ALT_VENV_PYTHON%"
if not exist "%PYTHON%" set "PYTHON=python"

set "SPEC_FILE=%ROOT%native-game2text.spec"
set "PACKAGING_DIR=%ROOT%build\packaging"
set "DIST_APP_DIR=%ROOT%dist\native-game2text"
set "TEMPLATE_CONFIG=%ROOT%config.template.ini"
set "PACKAGED_CONFIG=%PACKAGING_DIR%\config.ini"

if not exist "%SPEC_FILE%" (
  echo Missing spec file: %SPEC_FILE%
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

if exist "%PACKAGING_DIR%" rmdir /s /q "%PACKAGING_DIR%"
mkdir "%PACKAGING_DIR%" || exit /b 1
copy /y "%TEMPLATE_CONFIG%" "%PACKAGED_CONFIG%" >nul || exit /b 1

pushd "%ROOT%"
"%PYTHON%" -m PyInstaller --noconfirm --clean "%SPEC_FILE%"
set "BUILD_EXIT=%ERRORLEVEL%"
popd

if not "%BUILD_EXIT%"=="0" exit /b %BUILD_EXIT%

if not exist "%DIST_APP_DIR%" (
  echo Build finished but dist folder is missing: %DIST_APP_DIR%
  exit /b 1
)

if not exist "%DIST_APP_DIR%\logs\text" mkdir "%DIST_APP_DIR%\logs\text"
if not exist "%DIST_APP_DIR%\logs\images" mkdir "%DIST_APP_DIR%\logs\images"
copy /y "%ROOT%run_native_admin.bat" "%DIST_APP_DIR%\run_native_admin.bat" >nul

echo Build complete: %DIST_APP_DIR%
exit /b 0
