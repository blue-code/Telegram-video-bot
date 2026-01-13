@echo off
SETLOCAL
cd /d %~dp0
set OPENSSL_CONF=openssl_legacy.cnf
call venv_win\Scripts\activate.bat

echo Checking/Updating dependencies...
pip install -r requirements.txt --quiet

uvicorn src.server:app --host 0.0.0.0 --reload --port 8000
pause
ENDLOCAL
