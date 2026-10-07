#requires -Version 5.1
<#
Installs the newest TV Manager release if there is one. Run nightly by the
"TV Manager Auto Update" task (install-auto-deploy.ps1). Safe to run by hand:

  .\auto-update.ps1 -Check            # report only, change nothing
  .\auto-update.ps1                   # update now if a newer release exists
  .\auto-update.ps1 -Version 18.14.0  # install a specific newer release

Uses the base Python interpreter (not .venv) because the update may replace .venv.
Results: logs\auto-update.log and .runtime\auto-update-status.json.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = '',
    [switch]$Check,
    [ValidatePattern('^(\d+\.\d+\.\d+)?$')][string]$Version = ''
)
$ErrorActionPreference = 'Stop'
# Windows PowerShell 5.1 leaves the script path empty inside param() defaults; resolve it here.
if (!$InstallDir) { $InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$Root = (Resolve-Path -LiteralPath $InstallDir).ProviderPath
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $VenvPython -PathType Leaf)) { throw "Python environment not found: $VenvPython" }
$BasePython = & $VenvPython -I -c 'import sys; print(sys._base_executable)'
if ($LASTEXITCODE -ne 0 -or !$BasePython -or !(Test-Path -LiteralPath $BasePython -PathType Leaf)) {
    throw 'The installed Python environment is broken; repair it before updating.'
}
$Arguments = @('-I', (Join-Path $Root 'auto_update.py'), '--install-dir', $Root)
if ($Check) { $Arguments += '--check' }
if ($Version) { $Arguments += @('--version', $Version) }
$ErrorActionPreference = 'Continue'
& $BasePython @Arguments
exit $LASTEXITCODE
