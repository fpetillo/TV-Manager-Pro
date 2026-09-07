param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    [string]$Message = "Release v$Version"
)

$ErrorActionPreference = "Stop"
$Project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Project

Write-Host "TV Manager release push for v$Version" -ForegroundColor Cyan

Write-Host "Stopping local TV Manager processes..." -ForegroundColor Cyan
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Cleaning generated/runtime folders that should never be committed..." -ForegroundColor Cyan
$RemoveDirs = @("dist","build","release",".pytest_cache","__pycache__")
foreach ($d in $RemoveDirs) {
    if (Test-Path ".\$d") {
        Remove-Item ".\$d" -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path ".\$d") {
            cmd /c rmdir /s /q "\\?\$Project\$d"
        }
    }
}

Remove-Item ".\TVManager.spec" -Force -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Force -Include *.pyc,*.pyo -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "Ensuring .gitignore protects private/runtime/build files..." -ForegroundColor Cyan
$Required = @(
    ".env",
    "tvmanager.db",
    "*.db",
    "*.db-wal",
    "*.db-shm",
    "logs/",
    "diagnostics/",
    "backups/",
    "managed_trash/",
    "imports/",
    "db-emergency/",
    "corrupt-db/",
    ".venv/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    ".pytest_cache/",
    "build/",
    "dist/",
    "release/",
    "*.spec",
    "*.zip",
    "*.exe",
    "*.msi"
)
if (!(Test-Path ".\.gitignore")) { New-Item -ItemType File ".\.gitignore" | Out-Null }
$Existing = Get-Content ".\.gitignore" -Raw -ErrorAction SilentlyContinue
foreach ($line in $Required) {
    if ($Existing -notmatch [regex]::Escape($line)) {
        Add-Content ".\.gitignore" $line
        $Existing += "`n$line"
    }
}

Write-Host "Resetting partial staging..." -ForegroundColor Cyan
git reset

Write-Host "Adding source files safely..." -ForegroundColor Cyan
git add -- . `
  ':!dist' `
  ':!build' `
  ':!release' `
  ':!.venv' `
  ':!tvmanager.db' `
  ':!*.db' `
  ':!*.db-wal' `
  ':!*.db-shm' `
  ':!.env' `
  ':!logs' `
  ':!diagnostics' `
  ':!backups' `
  ':!managed_trash' `
  ':!imports' `
  ':!db-emergency' `
  ':!corrupt-db'

Write-Host "Staged changes:" -ForegroundColor Cyan
git status --short

$Changes = git diff --cached --name-only
if (!$Changes) {
    Write-Host "No staged changes to commit." -ForegroundColor Yellow
    exit 0
}

git commit -m $Message
git push

Write-Host "Release v$Version pushed to GitHub." -ForegroundColor Green
