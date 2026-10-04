# TV Manager Pro Windows service

The Windows x64 service ZIP includes TVManager.exe, its bundled Python runtime, WinSW 2.12.0, templates/assets and Manage-Service.ps1. Python and Git are not required on the destination. Keep the entire extracted folder together; this is not a single standalone EXE. Browser administrator login remains optional in Settings -> Security.

## Install or migrate the existing source installation

1. Finish active jobs, stop TV Manager and disable its old **TV Manager** / **TV Manager Production** logon task in Task Scheduler. Keep that task until service startup is verified. Do not run both startup methods.
2. Make a stopped-application backup of the existing installation, including the database and any WAL/SHM files, .env, session key, configuration and recovery history.
3. Extract the release ZIP elsewhere. Copy the **contents** of its TVManager folder into `C:\Acuityware TV Manager`. The package contains no database, credentials or .env, so existing state stays in place. Keep the existing installation path during this migration. The service account needs a writable installation; do not place this version under Program Files.
4. Open **PowerShell as administrator** and run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\Acuityware TV Manager\Manage-Service.ps1' -Action Install
```

5. At the Windows credential prompt, select an existing Windows account such as `SERVER\tvmanager` or `DOMAIN\tvmanager`. Use the Windows account password, not a Windows Hello PIN. The account must be accepted by your NAS/file server. The installer grants this account Log on as a service and Modify permission on this installation. It stores the password through Windows Service Control Manager, never in service XML or GitHub. Domain policy can override local account rights; a domain administrator may need to assign them.
6. Start:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\Acuityware TV Manager\Manage-Service.ps1' -Action Start
```

Open the configured URL (for example `http://192.168.1.11:5050`) and verify the version in About. New installations still default to localhost; configure Settings -> Network if needed. Windows service administration requires Windows administrator rights; this is independent of TV Manager's optional browser login.

## Controls and operation

Use the same command with `-Action Status`, `Stop`, `Restart` or `Uninstall`, or use Windows Services (`services.msc`) and select **TV Manager Pro**. Status reports the Windows account and executable. Uninstall removes only service registration, preserving files/data and account permissions. Install refuses to overwrite an existing service, and management commands refuse a service registered to a different installation.

The service starts automatically after boot with delayed startup and restarts on failure after 30, 60 and then 120 seconds. A Running service status means Windows started the wrapper; also verify the web page because application initialization can still fail. Logs are in `logs\service`, rotated at approximately 10 MB with eight retained files per stream.

Stop requests block new web work, stop new scheduler dispatches and wait up to 150 seconds for active HTTP requests, background jobs and imports. Timeout is logged as an incomplete shutdown. The wrapper has a 180-second stop timeout. Finish long-running transfers before maintenance; jobs that outlast shutdown or a forced Windows shutdown still require recovery review. There is no public HTTP shutdown endpoint.

## Network TV libraries

Use UNC paths such as `\\192.168.1.221\TV Shows`, not a mapped drive such as `T:` or an HTTP URL. A service has its own logon session and does not inherit your desktop drive mappings. Grant the selected account the share and filesystem permissions needed to read, create, rename and move files. An existing Explorer connection does not prove the service account can authenticate. On a NAS/workgroup network, configure an account the NAS accepts and test it from the running service. [Microsoft's guidance](https://learn.microsoft.com/en-us/windows/win32/services/services-and-redirected-drives).

Keep the database local. After installation verify each configured library path, a complete post-processing operation and media-server refresh under the service account, then reboot without signing in and verify the URL again. Network-share access and reboot acceptance must be performed on the destination server.

## Upgrading the packaged service

The source-only update-server.ps1 deliberately refuses packaged service installations: copying Python source would leave the EXE running old code. For a packaged update, finish jobs and stop the service, back up the installation, and overlay a new verified service ZIP's TVManager contents into the same directory. Preserve database/.env/session key and other runtime folders. Do not reinstall service registration for an ordinary upgrade; that retains its Windows account and startup settings. Start and verify the new version. If startup fails, keep it stopped and restore the matching pre-update binary/data backup before production resumes.

Packages are currently unsigned; verify the SHA-256 checksum published with the release. No unattended binary updater or signed MSI is claimed. WinSW's MIT license is included. Build instructions are in `installer/windows/build-service-package.ps1`; the build uses the developer's Python environment and does not install/start a service or copy operator data into the package.
