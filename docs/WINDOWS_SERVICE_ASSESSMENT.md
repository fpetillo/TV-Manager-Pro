# Windows EXE and service assessment — 2026-10-04

**Yes, a Windows service can use TV libraries on network shares.** Configure UNC paths such as `\\192.168.1.221\TV Shows`, and run the service under an account that the share accepts. Grant the account the share and filesystem permissions needed to read, create, rename and move episodes. For a NAS or workgroup server, verify its authentication against that account; access from an interactive desktop session does not prove access from the service. Microsoft recommends UNC paths for services because mapped drive letters belong to individual logon sessions: [Services and redirected drives](https://learn.microsoft.com/en-us/windows/win32/services/services-and-redirected-drives).

Browser login and the Windows service account are independent. Turning off TV Manager's optional browser login does not remove the service's need for permission to access its local database and network folders. A filesystem library uses UNC paths, not an HTTP URL. The browser would still open TV Manager at the configured address, for example `http://192.168.1.11:5050`.

## What the project already has

- `installer/windows/build-exe.ps1` bundles `server.py` with PyInstaller into `TVManager.exe` and stages templates/static assets beside it. This includes Python and its dependencies; the target server need not have a separate Python installation. [PyInstaller operating mode](https://pyinstaller.org/en/stable/operating-mode.html).
- `installer/windows/TVManager.iss` defines a per-user Inno Setup installation and launch shortcut. It does not register a Windows service.
- `app_paths.py` keeps frozen application data beside the installed EXE, outside the temporary extraction folder. That location must be writable by the service account. A future machine-wide installer should separate executable files from writable data, with migration and permissions tested.
- `install-production-startup.ps1` and `install-startup.ps1` create **logon scheduled tasks**, not services. `server.py` runs Waitress and the scheduler but does not implement Windows Service Control Manager registration or a service stop handler.
- The v18.11.x updater updates **source installations only**. It does not rebuild or replace a bundled EXE.

## Recommended implementation

Package a tested EXE distribution and add a Windows service wrapper, such as a pinned stable WinSW release. WinSW can manage an ordinary executable as a service: [official project](https://github.com/winsw/winsw). Its stable and prerelease documentation must be matched to the selected binary. A one-folder PyInstaller distribution is worth evaluating for predictable startup and upgrades; packaging as one EXE is not itself service registration.

Provide install/start/stop/status/uninstall operations, a configurable service account, delayed automatic startup, restart-on-failure and rotating logs. Store credentials through Windows service account configuration, not a committed XML file. Windows service installation requires Windows administrative rights; this is separate from optional TV Manager browser login. See [Microsoft service user accounts](https://learn.microsoft.com/en-us/windows/win32/services/service-user-accounts).

Add a controlled shutdown path that stops scheduling new work and handles active workers before service termination. Extend the updater to stop the service, back up state, replace a verified packaged release, restart and check its version, with rollback on failed startup. Prevent duplicate scheduling by retiring the old logon task during an explicitly selected service migration.

Before declaring it ready, test a reboot without interactive login, actual share access under the configured service account, a complete search/download/processing cycle, Plex refresh, network loss/recovery, safe stop during work and a packaged upgrade/rollback. Keep the SQLite database on local storage; network libraries remain separate.

## Status

This is an investigation and proposed implementation, not a new service installer or tested production EXE. No Windows service, account permissions, firewall rule or production startup configuration was changed. The current packaging scripts were inspected; no new binary was built in this investigation. Service shutdown behavior and access to the user's actual NAS/shares remain unverified.
