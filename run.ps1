$ErrorActionPreference="Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

$ProjectPython = Join-Path $Here ".venv\Scripts\python.exe"
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    & ".\.venv\Scripts\Activate.ps1"
}
if (!(Test-Path $ProjectPython)) {
    $ProjectPython = (Get-Command python).Source
}

Write-Host "TV Manager startup folder: $Here"
Write-Host "Python executable: $ProjectPython"
& $ProjectPython --version

Write-Host "Clearing stale Python cache folders..."
Get-ChildItem -Path . -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

$VersionPath = Join-Path $Here "VERSION"
$Version = Get-Content $VersionPath -ErrorAction SilentlyContinue
Write-Host "VERSION file: $VersionPath"
Write-Host "Starting TV Manager version $Version from $Here"

Write-Host "Creating verified database/config protection snapshot before startup..."
& $ProjectPython protect_db.py --startup --reason "startup-v$Version"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Startup protection could not create a verified backup. Continuing to the database safety check for detailed recovery guidance." -ForegroundColor Yellow
}

Write-Host "Repairing/verifying local database schema before startup..."
& $ProjectPython db_doctor.py
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "TV Manager stopped before startup because the database safety check failed." -ForegroundColor Red
    Write-Host "Do not continue building or running against this database until you restore a known-good backup." -ForegroundColor Yellow
    exit $LASTEXITCODE
}

Write-Host "Verifying registered support routes and build identity..."
& $ProjectPython -c "import app; required=['/about','/library-health','/routes','/api/version','/api/about','/api/routes','/api/build-info','/build-info']; routes={r.rule for r in app.app.url_map.iter_rules()}; print('Imported app.py:', app.__file__); print('Runtime VERSION:', app.APP_VERSION); print('Registered support routes: ' + ', '.join([p for p in required if p in routes])); missing=[p for p in required if p not in routes]; raise SystemExit('Missing support routes: '+','.join(missing) if missing else 0)"

& $ProjectPython app.py
