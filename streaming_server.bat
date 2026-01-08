@echo off
SETLOCAL
cd /d %~dp0
set OPENSSL_CONF=openssl_legacy.cnf
call venv_win\Scripts\activate.bat
uvicorn src.server:app --reload --port 8000
pause
ENDLOCAL
