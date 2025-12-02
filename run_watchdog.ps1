# Start Watchdog Script
# Sets execution policy, activates virtual environment, and runs watchdog

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

if (-not (Test-Path $VenvActivate)) {
    Write-Host "Error: Virtual environment not found at $VenvPath" -ForegroundColor Red
    Write-Host "Please create the virtual environment first using: python -m venv venv" -ForegroundColor Yellow
    exit 1
}

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

# Run the watchdog script
Write-Host "`nStarting watchdog..." -ForegroundColor Cyan
python watchdog.py

# Deactivate virtual environment
Write-Host "`nDeactivating virtual environment..." -ForegroundColor Cyan
deactivate

# Keep window open if there was an error
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nWatchdog exited with error code: $LASTEXITCODE" -ForegroundColor Red
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
