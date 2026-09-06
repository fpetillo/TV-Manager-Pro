$ErrorActionPreference="Stop"
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$Py=Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path $Py)) { $Py="python" }
Push-Location $Root
& $Py -m compileall -q .
if (!(Test-Path "dbcore.py") -or !(Test-Path "migrations.py")) { throw "database reliability modules missing." }
if (!(Test-Path "lifecycle.py") -or !(Test-Path "docs/ACQUISITION_LIFECYCLE.md")) { throw "v14 lifecycle files missing." }
if (!(Test-Path "naming.py") -or !(Test-Path "integrity.py") -or !(Test-Path "scheduler_guard.py")) { throw "v15 runtime modules missing." }
if (!(Test-Path "docs/NAMING.md") -or !(Test-Path "docs/WINDOWS_DEPLOYMENT.md") -or !(Test-Path "docs/RELEASE_NOTES_v15.md")) { throw "v15 documentation missing." }
if ($LASTEXITCODE -ne 0) { throw "Python compile validation failed." }
& $Py -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Unit tests failed." }
Write-Host "TV Manager release validation passed." -ForegroundColor Green
Pop-Location

if (!(Test-Path "docs/WINDOWS_FRESH_INSTALL.md")) { throw "Fresh Windows installation documentation missing." }

if (!(Test-Path "security.py") -or !(Test-Path "metadata_service.py")) { throw "v16 security modules missing." }
if (!(Test-Path "templates/login.html") -or !(Test-Path "templates/security_setup.html")) { throw "v16 security templates missing." }
if (!(Test-Path "docs/BROWSER_SECURITY.md") -or !(Test-Path "docs/RELEASE_NOTES_v16.md")) { throw "v16 documentation missing." }
