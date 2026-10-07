#requires -Version 5.1
<#
Starts TV Manager unattended. Used by the "TV Manager Production" startup task that
install-auto-deploy.ps1 registers; you can also run it by hand instead of run.ps1.

Same safety steps as run.ps1 (startup database snapshot, schema check), then runs the
server in its stoppable mode (server.py --service) so the auto-updater can stop it
gracefully. Exits at once while an update holds the maintenance flag, so the task's
restart-on-failure can never bring the old version back mid-update.
#>
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root
$Runtime = Join-Path $Root '.runtime'
$Logs = Join-Path $Root 'logs'
New-Item -ItemType Directory -Force -Path $Runtime, $Logs | Out-Null
$StartupLog = Join-Path $Logs 'startup.log'

function Write-StartupLog([string]$Message) {
    $line = '{0}  {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -LiteralPath $StartupLog -Value $line -Encoding UTF8
    Write-Host $line
}

if (Test-Path -LiteralPath (Join-Path $Runtime 'maintenance.json')) {
    Write-StartupLog 'Maintenance in progress (auto-update). Not starting.'
    exit 0
}
$Blocked = Join-Path $Runtime 'startup-blocked.json'
if (Test-Path -LiteralPath $Blocked) {
    Write-StartupLog "Startup is blocked by a failed database check. Fix the database, delete $Blocked, then start again."
    exit 1
}

$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $Python)) {
    Write-StartupLog "Python environment not found: $Python. Run setup.ps1 first."
    exit 1
}
$Version = (Get-Content -LiteralPath (Join-Path $Root 'VERSION') -ErrorAction SilentlyContinue | Select-Object -First 1)
Write-StartupLog "Starting TV Manager $Version from $Root"

Get-ChildItem -LiteralPath $Root -Directory -Recurse -Filter '__pycache__' -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

$ErrorActionPreference = 'Continue'
& $Python protect_db.py --startup --reason "startup-v$Version" *> $null
if ($LASTEXITCODE -ne 0) { Write-StartupLog 'Startup snapshot could not be verified; continuing to the database check.' }
$DoctorOutput = & $Python db_doctor.py 2>&1 | Out-String
$DoctorExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($DoctorExit -ne 0) {
    @{ blocked_at = (Get-Date).ToString('o'); exit_code = $DoctorExit; output = $DoctorOutput.Trim() } |
        ConvertTo-Json | Set-Content -LiteralPath $Blocked -Encoding UTF8
    Write-StartupLog "Database check failed (exit $DoctorExit). Startup blocked until reviewed:`n$DoctorOutput"
    exit 1
}

# Keep one previous console log for troubleshooting.
$OutLog = Join-Path $Logs 'server.out.log'
$ErrLog = Join-Path $Logs 'server.err.log'
foreach ($Log in @($OutLog, $ErrLog)) {
    if (Test-Path -LiteralPath $Log) { Move-Item -LiteralPath $Log -Destination ($Log + '.1') -Force }
}
$Server = Start-Process -FilePath $Python -ArgumentList @('server.py', '--service') -WorkingDirectory $Root `
    -NoNewWindow -Wait -PassThru -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
Write-StartupLog "TV Manager exited with code $($Server.ExitCode)."
exit $Server.ExitCode
