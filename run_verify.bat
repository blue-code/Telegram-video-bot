@echo off
SETLOCAL
cd /d %~dp0
call venv_win\Scripts\activate.bat
set "BOT_CONFLICT_EXIT=1"
:retry
python verify_phase4.py
if "%errorlevel%"=="2" (
  echo Conflict detected. Retrying in 5 seconds...
  timeout /t 5 /nobreak >nul
  goto retry
)
pause
ENDLOCAL
