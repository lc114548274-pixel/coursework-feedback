@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".demo_venv\Scripts\python.exe" (
    ".demo_venv\Scripts\python.exe" start_demo.py %*
    goto finished
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 start_demo.py %*
    goto finished
)
where python >nul 2>nul
if not errorlevel 1 (
    python start_demo.py %*
    goto finished
)
echo Please install Python 3.12 and enable Add Python to PATH, then run this file again.
pause
exit /b 1
:finished
if errorlevel 1 pause
