@echo off
SETLOCAL
cd /d %~dp0
call venv_win\Scripts\activate.bat
python get_channel_id.py
pause
ENDLOCAL
