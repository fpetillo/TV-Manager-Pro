$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Task = "TV Manager Production"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Server = Join-Path $Root "server.py"
if (!(Test-Path $Python)) { throw "Virtual environment not found. Run .\setup.ps1 first." }
$PreviousPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $Python -c "import waitress" *> $null
$WaitressExit = $LASTEXITCODE
$ErrorActionPreference = $PreviousPreference
if ($WaitressExit -ne 0) { throw "Waitress is not installed. Run .\setup.ps1 first." }

$Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$Server`"" -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet `
  -RestartCount 10 `
  -RestartInterval (New-TimeSpan -Minutes 1) `
  -StartWhenAvailable `
  -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $Task -Action $Action -Trigger $Trigger -Settings $Settings `
  -Description "TV Manager production server (Waitress) with scheduler recovery" -Force | Out-Null

Write-Host "TV Manager production startup task installed." -ForegroundColor Green
Write-Host "Task: $Task"
