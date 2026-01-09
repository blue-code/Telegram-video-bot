@echo off
SETLOCAL
cd /d %~dp0

echo ====================================
echo Telegram Video Bot - Start All
echo ====================================
echo.

REM 1. Run verification in background (new window)
echo [1/2] Starting verification...
start "TVB Verification" cmd /c run_verify.bat
echo.

REM Wait 2 seconds for verification to initialize
timeout /t 2 /nobreak >nul

REM 2. Start streaming server in current window
echo [2/2] Starting streaming server...
echo.
call streaming_server.bat

ENDLOCAL
