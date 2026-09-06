$ErrorActionPreference="Stop"
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
