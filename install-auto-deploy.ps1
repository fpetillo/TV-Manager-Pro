#requires -Version 5.1
<#
One-time setup of unattended running and automatic updates on the TV Manager server.
Run from an Administrator PowerShell on the server, in the installation folder:

  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install-auto-deploy.ps1

Creates two scheduled tasks that run as the Windows account you enter (it must be able
to open your UNC media shares):
  * TV Manager Production   - starts TV Manager at boot, no sign-in needed
                              (start-production.ps1, restarts on failure)
  * TV Manager Auto Update  - nightly: installs a newer GitHub release with a graceful
                              stop, verified backup, start check and automatic rollback
                              (auto-update.ps1)

Options:
  -UpdateTime 03:30   nightly check time (24-hour)
  -NoAutoUpdate       only set up unattended startup
  -Uninstall          remove both tasks (TV Manager keeps running until stopped)
Your password goes to Windows Task Scheduler only; it is not written anywhere else.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = '',
    [ValidatePattern('^([01]\d|2[0-3]):[0-5]\d$')][string]$UpdateTime = '03:30',
    [switch]$NoAutoUpdate,
    [switch]$Uninstall
)
$ErrorActionPreference = 'Stop'
# Windows PowerShell 5.1 leaves the script path empty inside param() defaults; resolve it here.
if (!$InstallDir) { $InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$ProductionTask = 'TV Manager Production'
$UpdateTask = 'TV Manager Auto Update'
$LegacyTask = 'TV Manager'

$Identity = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (!$Identity.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this from an Administrator PowerShell (right-click PowerShell > Run as administrator).'
}
$Root = (Resolve-Path -LiteralPath $InstallDir).ProviderPath

if ($Uninstall) {
    foreach ($Name in @($UpdateTask, $ProductionTask)) {
        if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $Name -Confirm:$false
            Write-Host "Removed scheduled task: $Name" -ForegroundColor Green
        }
    }
    Write-Host 'TV Manager keeps running until stopped. To stop it gracefully:'
    Write-Host "  & '$Root\.venv\Scripts\python.exe' '$Root\server.py' --stop-service"
    exit 0
}

# ---------------------------------------------------------------- checks
$Python = Join-Path $Root '.venv\Scripts\python.exe'
foreach ($Required in @('app.py', 'server.py', 'VERSION', 'start-production.ps1', 'auto-update.ps1', 'auto_update.py', 'update-server.ps1', 'tvmanager.db')) {
    if (!(Test-Path -LiteralPath (Join-Path $Root $Required))) {
        throw "$Required not found in $Root. Install TV Manager 18.14.0 or later here first (update-server.ps1)."
    }
}
if (!(Test-Path -LiteralPath $Python)) { throw "Python environment not found: $Python. Run setup.ps1 first." }
if (Test-Path -LiteralPath (Join-Path $Root 'TVManagerService.exe')) {
    throw 'This folder holds the packaged Windows service build. Automatic source updates do not apply to it.'
}
$Version = (Get-Content -LiteralPath (Join-Path $Root 'VERSION') | Select-Object -First 1).Trim()
Write-Host "TV Manager $Version at $Root"

Push-Location -LiteralPath $Root
try {
    $ErrorActionPreference = 'Continue'
    & $Python -c 'import waitress' *> $null
    $WaitressOk = ($LASTEXITCODE -eq 0)
    # Taking the one-instance lease fails if TV Manager is already running from this folder.
    & $Python -c 'import runtime_guard; runtime_guard.acquire(".")' *> $null
    $NotRunning = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = 'Stop'
} finally { Pop-Location }
if (!$WaitressOk) { throw 'Waitress is not installed in .venv. Run setup.ps1, then try again.' }
if (!$NotRunning) {
    throw 'TV Manager is running from this folder. Close its window (Ctrl+C in the run.ps1 window) and wait for it to exit, then run this again. The startup task will run it from now on.'
}

# ---------------------------------------------------------------- account
Write-Host ''
Write-Host 'Enter the Windows account TV Manager should run as. It must be able to open your media shares'
Write-Host '(for example \\192.168.1.221\Media). Use its Windows password, not a Hello PIN.'
$Default = "$env:USERDOMAIN\$env:USERNAME"
$Credential = Get-Credential -UserName $Default -Message 'Account for the TV Manager scheduled tasks'
if (!$Credential) { throw 'No account entered; nothing was changed.' }
$User = $Credential.UserName
$Password = $Credential.GetNetworkCredential().Password

# ---------------------------------------------------------------- tasks
$Shell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$StartAction = New-ScheduledTaskAction -Execute $Shell -WorkingDirectory $Root `
    -Argument ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f (Join-Path $Root 'start-production.ps1'))
$BootTrigger = New-ScheduledTaskTrigger -AtStartup
$BootTrigger.Delay = 'PT1M'
$StartSettings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 2) `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $ProductionTask -Action $StartAction -Trigger $BootTrigger -Settings $StartSettings `
    -User $User -Password $Password -RunLevel Limited -Force `
    -Description 'Runs TV Manager at boot without sign-in (start-production.ps1). Created by install-auto-deploy.ps1.' | Out-Null
Write-Host "Registered '$ProductionTask' (at startup, as $User)." -ForegroundColor Green

if (Get-ScheduledTask -TaskName $LegacyTask -ErrorAction SilentlyContinue) {
    Disable-ScheduledTask -TaskName $LegacyTask | Out-Null
    Write-Host "Disabled the older '$LegacyTask' sign-in task so TV Manager is not started twice." -ForegroundColor Yellow
}

if ($NoAutoUpdate) {
    if (Get-ScheduledTask -TaskName $UpdateTask -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $UpdateTask -Confirm:$false
        Write-Host "Removed '$UpdateTask'." -ForegroundColor Yellow
    }
} else {
    $UpdateAction = New-ScheduledTaskAction -Execute $Shell -WorkingDirectory $Root `
        -Argument ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f (Join-Path $Root 'auto-update.ps1'))
    $NightTrigger = New-ScheduledTaskTrigger -Daily -At $UpdateTime
    $UpdateSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 4) `
        -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $UpdateTask -Action $UpdateAction -Trigger $NightTrigger -Settings $UpdateSettings `
        -User $User -Password $Password -RunLevel Limited -Force `
        -Description 'Installs newer TV Manager releases from GitHub with backup and rollback (auto-update.ps1).' | Out-Null
    Write-Host "Registered '$UpdateTask' (daily at $UpdateTime, as $User)." -ForegroundColor Green
}
$Password = $null

$Config = Join-Path $Root 'auto_update.json'
if (!(Test-Path -LiteralPath $Config)) {
    [ordered]@{
        enabled = $true; repository = 'fpetillo/TV-Manager-Pro'; production_task = $ProductionTask
        max_wait_minutes = 120; busy_poll_minutes = 5; stop_timeout_seconds = 240
        start_timeout_seconds = 300; keep_backups = 5
    } | ConvertTo-Json | Set-Content -LiteralPath $Config -Encoding UTF8
    Write-Host "Wrote default settings to $Config (set enabled to false to pause updates)."
}

# ---------------------------------------------------------------- start and confirm
Remove-Item -LiteralPath (Join-Path $Root '.runtime\maintenance.json') -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName $ProductionTask
Write-Host 'Starting TV Manager through the startup task...'
$State = Join-Path $Root '.runtime\service.json'
$Deadline = (Get-Date).AddMinutes(3)
$Answered = $null
while ((Get-Date) -lt $Deadline -and !$Answered) {
    Start-Sleep -Seconds 5
    try {
        $Service = Get-Content -LiteralPath $State -Raw -ErrorAction Stop | ConvertFrom-Json
        $HostName = if ($Service.host -in @('0.0.0.0', '::', '')) { '127.0.0.1' } else { $Service.host }
        $Answered = Invoke-RestMethod -Uri ("http://{0}:{1}/api/version" -f $HostName, $Service.port) -TimeoutSec 10
        $Url = "http://{0}:{1}" -f $HostName, $Service.port
    } catch { }
}
if ($Answered) {
    Write-Host "TV Manager $($Answered.version) is running at $Url" -ForegroundColor Green
} else {
    Write-Host 'TV Manager did not answer within 3 minutes. Check logs\startup.log and logs\server.err.log.' -ForegroundColor Red
}

if (!$NoAutoUpdate) {
    Write-Host ''
    Write-Host 'Checking GitHub for releases (no changes are made by this check):'
    & $Shell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root 'auto-update.ps1') -Check
}
Write-Host ''
Write-Host 'Done. From now on, start/stop TV Manager with the scheduled task rather than run.ps1:'
Write-Host "  Start:  Start-ScheduledTask -TaskName '$ProductionTask'"
Write-Host "  Stop:   & '$Python' '$Root\server.py' --stop-service"
Write-Host "  Update now:  .\auto-update.ps1     Results: logs\auto-update.log"
