param(
    [Parameter(Mandatory=$true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"

$Project = "C:\Acuityware TV Manager"
Set-Location $Project

Write-Host "Stopping TV Manager..." -ForegroundColor Cyan
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Cleaning generated/runtime folders..." -ForegroundColor Cyan
$RemoveDirs = @(
    "dist",
    "build",
    "release",
    ".pytest_cache",
    "__pycache__"
)

foreach ($d in $RemoveDirs) {
    if (Test-Path ".\$d") {
        Remove-Item ".\$d" -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path ".\$d") {
            cmd /c rmdir /s /q "\\?\$Project\$d"
        }
    }
}

Write-Host "Removing generated spec/cache files..." -ForegroundColor Cyan
Remove-Item ".\TVManager.spec" -Force -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Force -Include *.pyc,*.pyo -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "Protecting .gitignore..." -ForegroundColor Cyan
$GitIgnoreRequired = @"

# Runtime/private files
.env
tvmanager.db
*.db
*.db-wal
*.db-shm

# Runtime folders
logs/
diagnostics/
backups/
managed_trash/
imports/
db-emergency/
corrupt-db/

# Python/cache/build
.venv/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
build/
dist/
release/
*.spec

# Packages/installers
*.zip
*.exe
*.msi

# Local OS/editor
.DS_Store
Thumbs.db
"@

if (!(Test-Path ".\.gitignore")) {
    $GitIgnoreRequired | Set-Content ".\.gitignore"
} else {
    $Existing = Get-Content ".\.gitignore" -Raw
    foreach ($line in $GitIgnoreRequired -split "`r?`n") {
        if ($line.Trim() -and $Existing -notmatch [regex]::Escape($line.Trim())) {
            Add-Content ".\.gitignore" $line
        }
    }
}

Write-Host "Git reset partial staging..." -ForegroundColor Cyan
git reset

Write-Host "Git status before add..." -ForegroundColor Cyan
git status --short

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

Write-Host "Git status after add..." -ForegroundColor Cyan
git status --short

$Changes = git diff --cached --name-only
if (!$Changes) {
    Write-Host "No staged changes to commit." -ForegroundColor Yellow
    exit 0
}

$Message = "Release v$Version"
Write-Host "Committing: $Message" -ForegroundColor Cyan
git commit -m $Message

Write-Host "Pushing to GitHub..." -ForegroundColor Cyan
git push

Write-Host "Done. v$Version pushed to GitHub." -ForegroundColor Green