<#
TV Manager Windows EXE build script

Builds a PyInstaller launcher and stages a clean Windows distribution without
recursively copying dist/build output back into itself.

Safe outputs:
  - PyInstaller work/dist/spec files: C:\Temp\TVManagerBuild\pyinstaller
  - Staged app payload:             C:\Temp\TVManagerBuild\stage\TVManager
  - Final distributable folder:      .\release\windows\TVManager
  - Launcher executable:             .\release\windows\TVManager\TVManager.exe
#>

$ErrorActionPreference = "Stop"

function Write-Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Remove-SafeDirectory($Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    if (Test-Path $Path) {
        Remove-Item $Path -Recurse -Force -ErrorAction Stop
    }
}

Write-Step "Preparing TV Manager Windows EXE build"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path $VenvPython)) {
    Write-Step "Creating project virtual environment"
    python -m venv .venv
}

if (!(Test-Path $VenvPython)) {
    throw "Could not find project Python at $VenvPython"
}

Write-Step "Upgrading build tooling"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt
& $VenvPython -m pip install pyinstaller

Write-Step "Verifying PyInstaller"
& $VenvPython -m PyInstaller --version | Out-Host

$BuildRoot = Join-Path $env:TEMP "TVManagerBuild"
$PyInstallerRoot = Join-Path $BuildRoot "pyinstaller"
$WorkPath = Join-Path $PyInstallerRoot "build"
$DistPath = Join-Path $PyInstallerRoot "dist"
$SpecPath = Join-Path $PyInstallerRoot "spec"
$StageRoot = Join-Path $BuildRoot "stage"
$StageApp = Join-Path $StageRoot "TVManager"
$ReleaseRoot = Join-Path $Root "release\windows"
$ReleaseApp = Join-Path $ReleaseRoot "TVManager"

Write-Step "Cleaning previous build output"
Remove-SafeDirectory $BuildRoot
Remove-SafeDirectory $ReleaseApp
New-Item -ItemType Directory -Force $WorkPath, $DistPath, $SpecPath, $StageApp, $ReleaseRoot | Out-Null

Write-Step "Building launcher EXE outside the project tree"
# PyInstaller analyzes server.py and imports the Flask application. Tell the
# application this is a packaging run so it does not open or repair the live
# operator database while building the EXE.
$PreviousBuildFlag = [Environment]::GetEnvironmentVariable("TVMANAGER_BUILDING_EXE", "Process")
[Environment]::SetEnvironmentVariable("TVMANAGER_BUILDING_EXE", "1", "Process")
try {
    & $VenvPython -m PyInstaller `
        --noconfirm `
        --clean `
        --name TVManager `
        --onefile `
        --workpath $WorkPath `
        --distpath $DistPath `
        --specpath $SpecPath `
        (Join-Path $Root "server.py")
}
finally {
    [Environment]::SetEnvironmentVariable("TVMANAGER_BUILDING_EXE", $PreviousBuildFlag, "Process")
}

$BuiltExe = Join-Path $DistPath "TVManager.exe"
if (!(Test-Path $BuiltExe)) {
    throw "PyInstaller completed but TVManager.exe was not found at $BuiltExe"
}

Write-Step "Staging clean application payload"
Write-Host "The live tvmanager.db and .env are intentionally excluded. Copy them into the installed folder after deployment." -ForegroundColor Yellow
$ExcludeDirs = @(
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "build",
    "dist",
    "release",
    "diagnostics",
    "logs",
    "backups",
    "managed_trash",
    "imports"
)

$ExcludeFiles = @(
    "tvmanager.db",
    "tvmanager.db-shm",
    "tvmanager.db-wal",
    ".env",
    "*.zip",
    "*.pyc",
    "*.pyo",
    "TVManager.spec"
)

$RoboArgs = @(
    $Root,
    $StageApp,
    "/E",
    "/NFL",
    "/NDL",
    "/NJH",
    "/NJS",
    "/NP",
    "/R:2",
    "/W:2",
    "/XD"
) + $ExcludeDirs + @("/XF") + $ExcludeFiles

Write-Host "robocopy source : $Root"
Write-Host "robocopy target : $StageApp"

# Important: use the PowerShell call operator with an argument array.
# Start-Process -ArgumentList flattens arrays into a single command line and
# can split paths containing spaces, causing ROBOCOPY to interpret
# C:\Acuityware TV Manager as source=C:\Acuityware, dest=...\TV, files=Manager.
& robocopy.exe @RoboArgs
$RoboExitCode = $LASTEXITCODE
if ($RoboExitCode -gt 7) {
    throw "robocopy staging failed with exit code $RoboExitCode"
}

Copy-Item $BuiltExe (Join-Path $StageApp "TVManager.exe") -Force

Write-Step "Publishing final Windows release folder"
Remove-SafeDirectory $ReleaseApp
Copy-Item $StageApp $ReleaseApp -Recurse -Force

Write-Host ""
Write-Host "Windows EXE build complete." -ForegroundColor Green
Write-Host "Final app folder : $ReleaseApp"
Write-Host "Launcher EXE     : $(Join-Path $ReleaseApp 'TVManager.exe')"
Write-Host ""
Write-Host "Next step: compile installer\windows\TVManager.iss with Inno Setup if you want a setup installer."
Write-Host "The Inno script should use: release\windows\TVManager\* as its source."
