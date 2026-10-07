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

function Stop-ProcessTree([int]$Id) {
    # The .venv python.exe is a launcher that starts the real interpreter as a child.
    try {
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$Id" -ErrorAction Stop |
            ForEach-Object { Stop-ProcessTree $_.ProcessId }
    } catch { }
    Stop-Process -Id $Id -Force -ErrorAction SilentlyContinue
}

function Invoke-StartupStep([string]$Name, [string[]]$Arguments, [int]$TimeoutMinutes) {
    # Output goes straight to files: capturing it through a PowerShell pipeline stalled
    # db_doctor.py under the scheduled task (no CPU use, never finished).
    $out = Join-Path $Logs "$Name.out.log"
    $err = Join-Path $Logs "$Name.err.log"
    $started = Get-Date
    $process = Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $Root -NoNewWindow -PassThru `
        -RedirectStandardOutput $out -RedirectStandardError $err
    $null = $process.Handle  # keeps ExitCode available after the process ends
    if (!$process.WaitForExit($TimeoutMinutes * 60 * 1000)) {
        Stop-ProcessTree $process.Id
        Write-StartupLog "$Name did not finish within $TimeoutMinutes minutes and was stopped. See logs\$Name.*.log."
        return @{ TimedOut = $true; ExitCode = $null; Output = '' }
    }
    $process.WaitForExit()
    $seconds = [int]((Get-Date) - $started).TotalSeconds
    $text = ((Get-Content -LiteralPath $out, $err -Raw -ErrorAction SilentlyContinue) -join "`n").Trim()
    Write-StartupLog "$Name finished in $seconds s (exit $($process.ExitCode))."
    return @{ TimedOut = $false; ExitCode = $process.ExitCode; Output = $text }
}

# Clear stale bytecode in TV Manager's own folders only (not .venv, backups or imports).
foreach ($Folder in @($Root, (Join-Path $Root 'tests'), (Join-Path $Root 'scripts'))) {
    $Cache = Join-Path $Folder '__pycache__'
    if (Test-Path -LiteralPath $Cache) { Remove-Item -LiteralPath $Cache -Recurse -Force -ErrorAction SilentlyContinue }
}

$Snapshot = Invoke-StartupStep 'protect_db' @('protect_db.py', '--startup', '--reason', "startup-v$Version") 10
if ($Snapshot.TimedOut -or $Snapshot.ExitCode -ne 0) {
    Write-StartupLog 'Startup snapshot could not be verified; continuing to the database check.'
}
$Doctor = Invoke-StartupStep 'db_doctor' @('db_doctor.py') 10
if ($Doctor.TimedOut) {
    # A stuck check is not a damaged database: fail this start so the task retries.
    exit 1
}
if ($Doctor.ExitCode -ne 0) {
    @{ blocked_at = (Get-Date).ToString('o'); exit_code = $Doctor.ExitCode; output = $Doctor.Output } |
        ConvertTo-Json | Set-Content -LiteralPath $Blocked -Encoding UTF8
    Write-StartupLog "Database check failed (exit $($Doctor.ExitCode)). Startup blocked until reviewed:`n$($Doctor.Output)"
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
