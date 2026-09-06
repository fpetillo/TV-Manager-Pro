$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Task = "TV Manager"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$App = Join-Path $Root "app.py"
if (!(Test-Path $Python)) { throw "Virtual environment not found. Run setup.ps1 first." }
$Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$App`"" -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
Register-ScheduledTask -TaskName $Task -Action $Action -Trigger $Trigger -Settings $Settings -Description "TV Manager automation platform" -Force | Out-Null
Write-Host "TV Manager startup task installed." -ForegroundColor Green
