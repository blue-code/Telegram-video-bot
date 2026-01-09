@echo off
SETLOCAL
cd /d %~dp0

echo ====================================
echo Telegram Video Bot - Virtual Environment Setup
echo ====================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.12 or higher
    pause
    exit /b 1
)

echo [1/5] Checking Python version...
python --version
echo.

REM Check if venv_win already exists
if exist venv_win (
    echo WARNING: venv_win directory already exists
    set /p "OVERWRITE=Do you want to delete and recreate it? (y/N): "
    if /i not "%OVERWRITE%"=="y" (
        echo Setup cancelled.
        pause
        exit /b 0
    )
    echo Deleting existing venv_win...
    rmdir /s /q venv_win
    echo.
)

echo [2/5] Creating virtual environment...
python -m venv venv_win
if %errorlevel% neq 0 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)
echo Virtual environment created successfully!
echo.

echo [3/5] Activating virtual environment...
call venv_win\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)
echo.

echo [4/5] Upgrading pip...
python -m pip install --upgrade pip
echo.

echo [5/5] Installing dependencies from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo.

echo ====================================
echo Setup completed successfully!
echo ====================================
echo.
echo To activate the virtual environment, run:
echo   venv_win\Scripts\activate.bat
echo.
echo To start the bot and server, run:
echo   start_all.bat
echo.
pause
ENDLOCAL
