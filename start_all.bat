@echo off
SETLOCAL
cd /d %~dp0

echo ====================================
echo Telegram Video Bot - Start All
echo ====================================
echo.

REM 1. Start Bot in background (new window)
echo [1/2] Starting Bot...
start "TVB Bot" cmd /c "call venv_win\Scripts\activate.bat && python -m src.bot"
echo.

REM 2. Start streaming server in current window
echo [2/2] Starting streaming server...
echo.
call streaming_server.bat

ENDLOCAL
