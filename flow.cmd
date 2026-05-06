@echo off
setlocal

cd /d "%~dp0"

echo Interview Flow - AI-Powered Interview Coach
echo ==================================================

rem Load .env if present (KEY=VALUE lines; lines starting with # are skipped)
if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
    )
)

rem Check Python version
python -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10+ required'" >nul 2>nul
if errorlevel 1 (
    echo Python 3.10+ is required
    pause
    exit /b 1
)

rem Use a Windows-specific venv so it never conflicts with a WSL-created .venv
if not exist ".venv-win\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv .venv-win
    if errorlevel 1 (
        echo.
        echo ERROR: Could not create virtual environment.
        echo Reinstall Python 3.10+ from https://python.org and include pip.
        pause
        exit /b 1
    )
)

echo Installing dependencies...
call .venv-win\Scripts\activate.bat
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

if not exist "data" mkdir data

echo.
echo Launching Interview Flow desktop app...
echo.

start "Interview Flow" /min python -m app.desktop
