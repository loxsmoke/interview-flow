@echo off
setlocal

cd /d "%~dp0\.."

if not defined E2E_PYTHON (
    set "E2E_PYTHON=%CD%\.venv-win\Scripts\python.exe"
)

if not exist "%E2E_PYTHON%" (
    echo Windows e2e tests require .venv-win. Run flow.cmd once to create it, or set E2E_PYTHON.
    exit /b 1
)

"%E2E_PYTHON%" -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo .venv-win exists but its Python is not working. Recreate .venv-win, then rerun this script.
    exit /b 1
)

"%E2E_PYTHON%" -c "import pytest" >nul 2>nul
if errorlevel 1 (
    echo Installing pytest into .venv-win...
    "%E2E_PYTHON%" -m pip install pytest
    if errorlevel 1 (
        exit /b 1
    )
)

if not exist "node_modules\.bin\playwright.cmd" (
    echo Installing Node dependencies...
    npm.cmd install
    if errorlevel 1 exit /b 1
)

set "CHROME_OK="
if exist "%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"       set "CHROME_OK=1"
if exist "%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"  set "CHROME_OK=1"
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"        set "CHROME_OK=1"
dir "%LOCALAPPDATA%\ms-playwright\chrome-win*" >nul 2>nul
if not errorlevel 1 set "CHROME_OK=1"

if not defined CHROME_OK (
    echo Installing Playwright Chrome browser...
    node_modules\.bin\playwright.cmd install chrome
    if errorlevel 1 exit /b 1
)

npm.cmd run test:e2e -- %*
