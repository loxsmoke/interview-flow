@echo off
setlocal

cd /d "%~dp0\.."

set "PYTHON="
if defined TEST_PYTHON (
    set "PYTHON=%TEST_PYTHON%"
)
if not defined PYTHON (
    set "PYTHON=.venv-win\Scripts\python.exe"
)

if not exist "%PYTHON%" (
    echo Windows tests require .venv-win. Run flow.cmd once to create it, or set TEST_PYTHON.
    exit /b 1
)

"%PYTHON%" -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo .venv-win exists but its Python is not working. Recreate .venv-win, then rerun this script.
    exit /b 1
)

"%PYTHON%" -c "import pytest" >nul 2>nul
if errorlevel 1 (
    echo Installing pytest into the selected Python environment...
    "%PYTHON%" -m pip install pytest
    if errorlevel 1 exit /b 1
)

if not exist "tests\.tmp" mkdir "tests\.tmp"
set "TMP=%CD%\tests\.tmp"
set "TEMP=%CD%\tests\.tmp"
set "PYTEST_TEMP=tests\.tmp\pytest-temp-%RANDOM%-%RANDOM%"

if "%~1"=="" (
    "%PYTHON%" -m pytest tests\app --basetemp="%PYTEST_TEMP%" -o cache_dir=tests\.tmp\pytest-cache
) else (
    "%PYTHON%" -m pytest --basetemp="%PYTEST_TEMP%" -o cache_dir=tests\.tmp\pytest-cache %*
)
