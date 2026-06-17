@echo off
chcp 65001 >nul 2>&1

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Please install Python 3.7+
    echo https://www.python.org/downloads/
    pause
    exit /b
)

pip install requests -q 2>nul

if "%~1"=="" (
    python "%~dp0qzone_download.py" --interactive
) else (
    python "%~dp0qzone_download.py" %*
)

pause
