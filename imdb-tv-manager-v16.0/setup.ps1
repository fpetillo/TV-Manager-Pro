$ErrorActionPreference="Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "TV Manager Windows Setup" -ForegroundColor Cyan
Write-Host "Location: $Root"

if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Install 64-bit Python 3.12 or 3.13, add it to PATH, reopen PowerShell, and run setup.ps1 again."
}

if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment..."
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -m venv .venv
    } else {
        python -m venv .venv
    }
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path $Python)) { throw "Virtual environment creation failed: $Python was not created." }

Write-Host "Updating pip..."
& $Python -m pip install --upgrade pip

Write-Host "Installing TV Manager dependencies..."
& $Python -m pip install -r requirements.txt

Write-Host "Verifying required runtime modules..."
& $Python -c "import flask, requests, dotenv, waitress; print('Runtime dependencies OK')"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Add your TMDb bearer token before using metadata search." -ForegroundColor Yellow
} else {
    Write-Host "Existing .env preserved." -ForegroundColor Green
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Initial/test runner:  .\run.ps1"
Write-Host "Production runner:    .\run-prod.ps1"
Write-Host "Health check:         .\status.ps1"
Write-Host "Fresh PC instructions: docs\WINDOWS_FRESH_INSTALL.md"
