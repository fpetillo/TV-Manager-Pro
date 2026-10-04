#requires -Version 5.1
[CmdletBinding()]
param([string]$OutputDir)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).ProviderPath
$Version = (Get-Content -LiteralPath (Join-Path $Root 'VERSION') -Raw).Trim()
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (!$OutputDir) { $OutputDir = Join-Path $Root "release\windows-service\v$Version" }
$OutputDir = [IO.Path]::GetFullPath($OutputDir)
if (Test-Path -LiteralPath $OutputDir) { throw 'Choose a new output directory; builds never erase existing output.' }
& $Python -m PyInstaller --version
if ($LASTEXITCODE -ne 0) { throw 'Install the build-only PyInstaller dependency before building.' }
New-Item -ItemType Directory -Path $OutputDir | Out-Null
$BuildRoot = Join-Path $env:TEMP ('TVManagerServiceBuild-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $BuildRoot | Out-Null
$OldFlag = $env:TVMANAGER_BUILDING_EXE
try {
    $env:TVMANAGER_BUILDING_EXE = '1'
    $Hidden = @()
    Get-ChildItem -LiteralPath $Root -Filter '*.py' -File | ForEach-Object { $Hidden += @('--hidden-import', $_.BaseName) }
    & $Python -m PyInstaller --noconfirm --clean --onedir --name TVManager --workpath (Join-Path $BuildRoot 'work') --specpath $BuildRoot --distpath $OutputDir @Hidden (Join-Path $Root 'server.py')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
} finally { $env:TVMANAGER_BUILDING_EXE = $OldFlag }
$Payload = Join-Path $OutputDir 'TVManager'
foreach ($Name in @('VERSION','RELEASE_MANIFEST.json','settings_defaults.json')) { Copy-Item -LiteralPath (Join-Path $Root $Name) -Destination $Payload }
foreach ($Name in @('static','templates')) { Copy-Item -LiteralPath (Join-Path $Root $Name) -Destination $Payload -Recurse }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Manage-Service.ps1') -Destination $Payload
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'TVManagerService.xml') -Destination $Payload
Copy-Item -LiteralPath (Join-Path $Root 'docs\WINDOWS_SERVICE.md') -Destination (Join-Path $Payload 'README-SERVICE.md')
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$Wrapper = Join-Path $Payload 'TVManagerService.exe'
Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe' -OutFile $Wrapper
if ((Get-FileHash -LiteralPath $Wrapper -Algorithm SHA256).Hash -ine '05b82d46ad331cc16bdc00de5c6332c1ef818df8ceefcd49c726553209b3a0da') { throw 'WinSW checksum mismatch.' }
$License = Join-Path $Payload 'WinSW-LICENSE.txt'
Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/winsw/winsw/v2.12.0/LICENSE.txt' -OutFile $License
if ((Get-FileHash -LiteralPath $License -Algorithm SHA256).Hash -ine '1cdf703c10a70e5973bf3acf2a5eeabe7746237155b92db2034aeae26fdf7802') { throw 'WinSW license checksum mismatch.' }
$Files = @(Get-ChildItem -LiteralPath $Payload -Recurse -File | ForEach-Object {
    @{path=$_.FullName.Substring($Payload.Length + 1).Replace('\','/');sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
})
@{version=$Version;architecture='Windows x64';wrapper='WinSW 2.12.0';files=$Files} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Payload 'PACKAGE_MANIFEST.json') -Encoding UTF8
$Zip = Join-Path $OutputDir "TVManagerPro-Service-v$Version-win-x64.zip"
Compress-Archive -LiteralPath $Payload -DestinationPath $Zip -CompressionLevel Optimal
$Hash = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText($Zip + '.sha256', "$Hash  $([IO.Path]::GetFileName($Zip))`n")
Write-Host "Service package: $Zip"
Write-Host "SHA256: $Hash"
Write-Host 'Build only. No Windows service was installed or started.'
