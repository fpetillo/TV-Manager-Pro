# TV Manager v18.12.0 â€” Windows service package

This release adds a Windows x64 EXE distribution with a WinSW 2.12.0 service host. Python and Git are not required on the destination. The complete distribution folder is required, including `_internal`, templates and static assets.

`Manage-Service.ps1` provides Install, Start, Stop, Restart, Status and Uninstall actions. Installation selects a Windows account, grants Log on as a service and installation-folder access, and configures delayed automatic startup and restart-on-failure. Credentials are passed to Windows Service Control Manager, not written to XML. Logs rotate in `logs/service`. Existing logon tasks must be disabled before installation, and the application must be stopped. Existing service registration is not silently overwritten.

The service's local stop command refuses new requests, stops scheduler dispatch and waits up to 150 seconds for active HTTP/background/import work. Timeout is reported as incomplete shutdown. The wrapper permits 180 seconds before forced termination. Finish long transfers before maintenance; forced shutdown still requires recovery review.

**Browser login remains optional**, as introduced in v18.11.2. Windows service administration rights and the service account's network-share permissions are separate from TV Manager browser authentication. Use UNC library paths and verify access under the actual service account.

Read [installation, migration and upgrade instructions](WINDOWS_SERVICE.md). The source updater refuses packaged service installations because replacing source does not update a bundled EXE. Packaged upgrades use a stopped-app backup and verified ZIP overlay while preserving runtime data and existing service registration.

Builds download a pinned, SHA-256-checked WinSW wrapper and license, stage only application assets/configuration defaults, and emit a ZIP/checksum and per-file manifest. No operator database, credentials or runtime history is included. Packages are currently unsigned.

Validation: 518 tests passed, two existing Windows symbolic-link privilege tests skipped; 72 Python modules, 43 JavaScript files, changed PowerShell scripts and dependency consistency passed. The actual compiled EXE served v18.12.0 and optional-login Settings, retained settings/session key after restart, and stopped successfully through its local service control. A real Waitress fixture drained an active job before exit. WinSW binary/license hashes and configuration parsing passed. This workstation lacks Windows administrative rights, so SCM registration, account-rights application and actual boot/service testing were not performed. The installer correctly refused a non-elevated registration attempt. Full details are recorded in RELEASE_MANIFEST.json. Destination Windows service registration, real share access and reboot without interactive login must be verified on the server; no production deployment is claimed.
