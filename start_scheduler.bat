@echo off
REM Start the Python scheduler in hidden background mode
REM This script can be used with Windows Task Scheduler or Startup folder

cd /d "%~dp0"

REM Start scheduler.py hidden (no window)
start /B pythonw scheduler.py

echo Scheduler started in background
timeout /t 2 /nobreak >nul

REM Verify PID file was created
if exist scheduler.pid (
    echo SUCCESS: Scheduler is running
    set /p PID=<scheduler.pid
    echo Process ID: %PID%
) else (
    echo WARNING: PID file not found, scheduler may not have started
)
