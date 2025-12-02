# Scheduler Control Script (PowerShell wrapper)
# Platform-agnostic utility to control the scheduler service
#
# Usage:
#   .\scheduler_ctl.ps1 status    - Check if scheduler is running
#   .\scheduler_ctl.ps1 start     - Start the scheduler
#   .\scheduler_ctl.ps1 stop      - Stop the scheduler
#   .\scheduler_ctl.ps1 restart   - Restart the scheduler

param(
    [Parameter(Position=0, Mandatory=$false)]
    [ValidateSet('status', 'start', 'stop', 'restart', 'help', '-h', '--help')]
    [string]$Command = 'help'
)

# Get the script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Navigate to script directory
Set-Location $ScriptDir

# Check if venv exists
$VenvPath = Join-Path $ScriptDir "venv"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "Error: Virtual environment not found at $VenvPath" -ForegroundColor Red
    Write-Host "Please create the virtual environment first using: python -m venv venv" -ForegroundColor Yellow
    exit 1
}

# Show help
if ($Command -in 'help', '-h', '--help') {
    Write-Host "Scheduler Control Script" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor White
    Write-Host "  .\scheduler_ctl.ps1 status    - Check if scheduler is running" -ForegroundColor Gray
    Write-Host "  .\scheduler_ctl.ps1 start     - Start the scheduler in background" -ForegroundColor Gray
    Write-Host "  .\scheduler_ctl.ps1 stop      - Stop the scheduler gracefully" -ForegroundColor Gray
    Write-Host "  .\scheduler_ctl.ps1 restart   - Stop and start the scheduler" -ForegroundColor Gray
    Write-Host "  .\scheduler_ctl.ps1 help      - Show this help message" -ForegroundColor Gray
    Write-Host ""
    exit 0
}

# Run the Python scheduler_ctl.py script with the given command
$PythonScript = Join-Path $ScriptDir "scheduler_ctl.py"

try {
    # Use the venv Python to run the control script
    & $PythonExe $PythonScript $Command
    
    # Return the exit code from Python
    exit $LASTEXITCODE
}
catch {
    Write-Host "Error running scheduler control script: $_" -ForegroundColor Red
    exit 1
}
