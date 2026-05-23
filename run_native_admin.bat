@echo off
setlocal

set "HERE=%~dp0"
set "TARGET_EXE=%HERE%native-game2text.exe"
set "SOURCE_PYTHON=%HERE%venv\Scripts\python.exe"
if not exist "%SOURCE_PYTHON%" set "SOURCE_PYTHON=%HERE%.venv\Scripts\python.exe"

if exist "%TARGET_EXE%" (
  powershell.exe -ExecutionPolicy Bypass -Command "Start-Process -Verb RunAs -FilePath '%TARGET_EXE%' -WorkingDirectory '%HERE%'"
  exit /b %ERRORLEVEL%
)

if exist "%SOURCE_PYTHON%" (
  powershell.exe -ExecutionPolicy Bypass -Command "Start-Process -Verb RunAs -FilePath '%SOURCE_PYTHON%' -ArgumentList 'native_app.py' -WorkingDirectory '%HERE%'"
  exit /b %ERRORLEVEL%
)

echo Could not find native-game2text.exe or a local virtual environment python.
exit /b 1
