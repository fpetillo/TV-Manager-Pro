#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('Install','Start','Stop','Restart','Status','Uninstall')]
    [string]$Action = 'Status',
    [string]$InstallDir = '',
    [System.Management.Automation.PSCredential]$Credential
)
$ErrorActionPreference = 'Stop'
$ServiceName = 'TVManagerPro'
if (!$InstallDir) { $InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$Root = (Resolve-Path -LiteralPath $InstallDir).ProviderPath
$Wrapper = Join-Path $Root 'TVManagerService.exe'

function Require-Administrator {
    $Principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (!$Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Open PowerShell with Run as administrator to manage the Windows service. This does not enable TV Manager browser login.'
    }
}

function Invoke-ServiceConfig([string[]]$Arguments) {
    & "$env:SystemRoot\System32\sc.exe" @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Windows service configuration failed with exit code $LASTEXITCODE." }
}

function Assert-OwnedService {
    $Existing = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'"
    if (!$Existing) { throw 'TV Manager Pro service is not installed.' }
    if ($Existing.PathName.Trim('"') -ine $Wrapper) {
        throw "The service belongs to another installation: $($Existing.PathName). Use its installation directory."
    }
    return $Existing
}

function Grant-ServiceLogon([string]$Account) {
    # Grant exactly SeServiceLogonRight to the selected account. Credentials go
    # directly to Windows through New-Service, never into XML or a command line.
    if (!('TVManagerServiceRights' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Principal;
public static class TVManagerServiceRights {
    [StructLayout(LayoutKind.Sequential)] struct Attributes {
        public uint Length; public IntPtr RootDirectory, ObjectName;
        public uint Flags; public IntPtr SecurityDescriptor, SecurityQualityOfService;
    }
    [StructLayout(LayoutKind.Sequential)] struct LsaString {
        public ushort Length, MaximumLength; public IntPtr Buffer;
    }
    [DllImport("advapi32.dll")] static extern uint LsaOpenPolicy(IntPtr system, ref Attributes attrs, uint access, out IntPtr policy);
    [DllImport("advapi32.dll")] static extern uint LsaAddAccountRights(IntPtr policy, IntPtr sid, LsaString[] rights, uint count);
    [DllImport("advapi32.dll")] static extern uint LsaNtStatusToWinError(uint status);
    [DllImport("advapi32.dll")] static extern uint LsaClose(IntPtr policy);
    public static void Grant(string account) {
        var identity = (SecurityIdentifier)new NTAccount(account).Translate(typeof(SecurityIdentifier));
        byte[] bytes = new byte[identity.BinaryLength]; identity.GetBinaryForm(bytes, 0);
        IntPtr sid = Marshal.AllocHGlobal(bytes.Length), policy = IntPtr.Zero;
        string right = "SeServiceLogonRight";
        var value = new LsaString { Length = (ushort)(right.Length * 2), MaximumLength = (ushort)((right.Length + 1) * 2), Buffer = Marshal.StringToHGlobalUni(right) };
        try {
            Marshal.Copy(bytes, 0, sid, bytes.Length);
            var attrs = new Attributes { Length = (uint)Marshal.SizeOf(typeof(Attributes)) };
            uint result = LsaOpenPolicy(IntPtr.Zero, ref attrs, 0x810, out policy);
            if (result != 0) throw new Win32Exception((int)LsaNtStatusToWinError(result));
            result = LsaAddAccountRights(policy, sid, new[] { value }, 1);
            if (result != 0) throw new Win32Exception((int)LsaNtStatusToWinError(result));
        } finally { if (policy != IntPtr.Zero) LsaClose(policy); Marshal.FreeHGlobal(sid); Marshal.FreeHGlobal(value.Buffer); }
    }
}
'@
    }
    [TVManagerServiceRights]::Grant($Account)
}

function Stop-TVManagerService {
    $Service = Get-Service -Name $ServiceName
    if ($Service.Status -ne 'Stopped') {
        $Service.Stop()
        $Service.WaitForStatus('Stopped', [TimeSpan]::FromSeconds(190))
    }
}

try {
    if ($Action -ne 'Status') { Require-Administrator }
    if ($Action -eq 'Install') {
        if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
            throw 'TV Manager Pro is already installed. Use Status/Start/Stop/Restart, or uninstall its registration first to change accounts.'
        }
        foreach ($Name in @('TVManager.exe','TVManagerService.exe','TVManagerService.xml','PACKAGE_MANIFEST.json')) {
            if (!(Test-Path -LiteralPath (Join-Path $Root $Name) -PathType Leaf)) { throw "Package file missing: $Name" }
        }
        $Manifest = Get-Content -LiteralPath (Join-Path $Root 'PACKAGE_MANIFEST.json') -Raw | ConvertFrom-Json
        foreach ($File in $Manifest.files) {
            $Target = [IO.Path]::GetFullPath((Join-Path $Root $File.path))
            if (!$Target.StartsWith($Root.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid package path.' }
            if ((Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash -ine $File.sha256) { throw "Package verification failed: $($File.path)" }
        }
        foreach ($TaskName in @('TV Manager','TV Manager Production')) {
            $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
            if ($Task -and $Task.State -ne 'Disabled') {
                throw "Disable the existing '$TaskName' scheduled task before installing the service, to avoid duplicate startup."
            }
        }
        # Hold the existing app's byte-range lease throughout registration.
        $Runtime = Join-Path $Root '.runtime'
        New-Item -ItemType Directory -Path $Runtime -Force | Out-Null
        $Lease = [IO.File]::Open((Join-Path $Runtime '.media-files.lock'), 'OpenOrCreate', 'ReadWrite', 'ReadWrite')
        try {
            if ($Lease.Length -eq 0) { $Lease.WriteByte(48); $Lease.Flush() }
            try { $Lease.Lock(0,1) } catch { throw 'TV Manager is running. Finish jobs and stop it before service installation.' }
            if (!$Credential) { $Credential = Get-Credential -Message 'Windows account that can access the TV library shares (SERVER\user or DOMAIN\user)' }
            if (!$Credential) { throw 'Service account selection was cancelled.' }
            Grant-ServiceLogon $Credential.UserName
            & "$env:SystemRoot\System32\icacls.exe" $Root /grant ('{0}:(OI)(CI)M' -f $Credential.UserName) | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'Could not grant the selected service account access to the installation.' }
            New-Service -Name $ServiceName -DisplayName 'TV Manager Pro' -BinaryPathName ('"' + $Wrapper + '"') -StartupType Automatic -Credential $Credential -Description 'TV Manager Pro library management and automation server.' | Out-Null
            Invoke-ServiceConfig -Arguments @('config', $ServiceName, 'start=', 'delayed-auto')
            Invoke-ServiceConfig -Arguments @('failure', $ServiceName, 'reset=', '86400', 'actions=', 'restart/30000/restart/60000/restart/120000')
        } finally { $Lease.Dispose() }
        Write-Host 'Service installed with automatic delayed startup. Use -Action Start when ready.' -ForegroundColor Green
    } else {
        $Existing = Assert-OwnedService
        switch ($Action) {
            'Start' { Start-Service -Name $ServiceName; (Get-Service $ServiceName).WaitForStatus('Running', [TimeSpan]::FromSeconds(45)) }
            'Stop' { Stop-TVManagerService }
            'Restart' { Stop-TVManagerService; Start-Service -Name $ServiceName }
            'Uninstall' { Stop-TVManagerService; Invoke-ServiceConfig -Arguments @('delete', $ServiceName); Write-Host 'Service registration removed. Application, database, libraries and account permissions retained.' }
            'Status' { $Existing | Select-Object Name, State, StartMode, StartName, PathName }
        }
    }
    if ($Action -in @('Start','Restart')) {
        Write-Host 'Windows reports the service started. Confirm TV Manager opens at its configured URL and check logs\service for startup errors.'
    }
} catch {
    Write-Error $_
    exit 1
}
