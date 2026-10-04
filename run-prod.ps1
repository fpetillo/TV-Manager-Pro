param([string]$ListenAddress, [int]$Port)
$ErrorActionPreference="Stop"
if ($PSBoundParameters.ContainsKey('ListenAddress')) { $env:TVMANAGER_BIND_HOST = $ListenAddress }
if ($PSBoundParameters.ContainsKey('Port')) { $env:TVMANAGER_BIND_PORT = [string]$Port }
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path $Python)) { throw "Virtual environment not found. Run .\setup.ps1 first." }
$PreviousPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $Python -c "import waitress" *> $null
$WaitressExit = $LASTEXITCODE
$ErrorActionPreference = $PreviousPreference
if ($WaitressExit -ne 0) { throw "Waitress is not installed. Run .\setup.ps1 to update dependencies." }
& $Python server.py
