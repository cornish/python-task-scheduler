# Activate Virtual Environment Script
# Sets execution policy and activates the virtual environment

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
    Write-Host "`nYou can now run Python commands in this virtual environment." -ForegroundColor Yellow
    Write-Host "To deactivate, type: deactivate" -ForegroundColor Yellow
} else {
    Write-Host "Warning: Virtual environment activation may have failed" -ForegroundColor Red
}
