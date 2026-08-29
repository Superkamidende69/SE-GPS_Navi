@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if not errorlevel 1 (
  py -3 server.py
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python 3 was not found. Install Python 3 and make sure it is added to PATH.
    pause
    exit /b 1
  )
  python server.py
)

pause
