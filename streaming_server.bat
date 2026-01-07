@echo off
SETLOCAL
cd /d %~dp0
call venv_win\Scripts\activate.bat
uvicorn src.server:app --reload --port 8000
pause
ENDLOCAL
