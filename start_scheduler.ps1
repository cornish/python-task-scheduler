# Start Scheduler Script
# Sets execution policy, activates virtual environment, and runs scheduler
# 
# Usage:
#   .\start_scheduler.ps1                    - Run in foreground (interactive mode)
#   .\start_scheduler.ps1 -Background        - Run in background (daemon mode)
#   .\start_scheduler.ps1 -bg                - Run in background (daemon mode)
#   .\start_scheduler.ps1 background         - Run in background (daemon mode)
#   .\start_scheduler.ps1 bg                 - Run in background (daemon mode)

param(
    [Parameter(Position=0)]
    [string]$Mode,
    
    [Alias("bg")]
    [switch]$Background
)

# Check if background mode was requested (case-insensitive)
$IsBackgroundMode = $Background -or ($Mode -match '^(background|bg)$')

# Set execution policy for current user (no admin rights needed)
Write-Host "Setting execution policy for current user..." -ForegroundColor Cyan
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force

# Get the script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Navigate to script directory
Set-Location $ScriptDir

# Check if venv exists
$VenvPath = Join-Path $ScriptDir "venv"
$VenvActivate = Join-Path $VenvPath "Scripts\Activate.ps1"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"
$PythonwExe = Join-Path $VenvPath "Scripts\pythonw.exe"
$PidFile = Join-Path $ScriptDir "scheduler.pid"

if (-not (Test-Path $VenvActivate)) {
    Write-Host "Error: Virtual environment not found at $VenvPath" -ForegroundColor Red
    Write-Host "Please create the virtual environment first using: python -m venv venv" -ForegroundColor Yellow
    exit 1
}

if ($IsBackgroundMode) {
    # ===== BACKGROUND MODE =====
    Write-Host "`nStarting scheduler in background mode..." -ForegroundColor Cyan
    
    # Use pythonw.exe (windowless Python) from venv for background execution
    $SchedulerScript = Join-Path $ScriptDir "scheduler.py"
    
    if (Test-Path $PythonwExe) {
        # Start the process hidden in the background
        $ProcessInfo = New-Object System.Diagnostics.ProcessStartInfo
        $ProcessInfo.FileName = $PythonwExe
        $ProcessInfo.Arguments = "`"$SchedulerScript`""
        $ProcessInfo.WorkingDirectory = $ScriptDir
        $ProcessInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
        $ProcessInfo.CreateNoWindow = $true
        
        $Process = [System.Diagnostics.Process]::Start($ProcessInfo)
        
        Write-Host "Scheduler started in background" -ForegroundColor Green
        
        # Wait a moment for the PID file to be created
        Start-Sleep -Seconds 2
        
        # Verify PID file was created
        if (Test-Path $PidFile) {
            $ProcessID = Get-Content $PidFile
            Write-Host "SUCCESS: Scheduler is running" -ForegroundColor Green
            Write-Host "Process ID: $ProcessID" -ForegroundColor White
            Write-Host "`nTo stop the scheduler, use: python scheduler_ctl.py stop" -ForegroundColor Yellow
        } else {
            Write-Host "WARNING: PID file not found, scheduler may not have started" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Error: pythonw.exe not found in virtual environment" -ForegroundColor Red
        exit 1
    }
    
} else {
    # ===== FOREGROUND MODE =====
    
    # Activate virtual environment
    Write-Host "Activating virtual environment..." -ForegroundColor Cyan
    & $VenvActivate
    
    # Check if activation was successful
    if ($LASTEXITCODE -eq 0 -or $env:VIRTUAL_ENV) {
        Write-Host "Virtual environment activated successfully" -ForegroundColor Green
        Write-Host "Python location: $(Get-Command python | Select-Object -ExpandProperty Source)" -ForegroundColor Gray
    } else {
        Write-Host "Warning: Virtual environment activation may have failed" -ForegroundColor Yellow
    }
    
    # Run the scheduler script in foreground
    Write-Host "`nStarting scheduler in foreground mode..." -ForegroundColor Cyan
    Write-Host "(Press Ctrl+C to stop)`n" -ForegroundColor Gray
    python scheduler.py
    
    # Deactivate virtual environment
    Write-Host "`nDeactivating virtual environment..." -ForegroundColor Cyan
    deactivate
    
    # Keep window open if there was an error
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nScheduler exited with error code: $LASTEXITCODE" -ForegroundColor Red
        Write-Host "Press any key to exit..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
}
