# TV Manager v18.11.0 — Network access and installation readiness

The normal launcher previously always listened on 127.0.0.1. Settings → Network now saves a listening IP address and port shared by run.ps1, run-prod.ps1 and the packaged server entry point. Saving does not interrupt active jobs; the page shows the current address, pending address and restart instructions. A specific address must belong to the installed computer. Use 0.0.0.0 to listen on all IPv4 interfaces, or 127.0.0.1 for local-only access.

## Set this installation to 192.168.1.11:5050

1. Update the source using the procedure below, then start TV Manager locally.
2. On the installed server, open http://127.0.0.1:5050/settings#security. If needed, create an administrator password and enable **Require browser login**, then sign in. The existing LAN authentication requirement is retained.
3. Open **Settings → Network**. Set **Listening IP address** to `192.168.1.11` and **Port** to `5050`.
4. Click **Save Network Settings**. Finish active jobs and restart TV Manager normally. For ongoing service use, prefer `run-prod.ps1`.
5. Open http://192.168.1.11:5050 from the server or another computer and sign in. Settings → Network should say the saved settings are active. A listener bound only to that address no longer accepts 127.0.0.1 connections.

If other computers cannot connect but the address works on the server, check the Windows network profile and firewall. This optional command in an administrator PowerShell allows port 5050 from the local subnet on the Private profile:

```powershell
New-NetFirewallRule -DisplayName "TV Manager TCP 5050" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5050 -Profile Private -RemoteAddress LocalSubnet
```

The application does not automatically create firewall rules. Do not change a public network to Private unless it is your trusted LAN. A Domain-managed server may require its normal administrator-managed firewall policy.

## Configuration and recovery

The address/port are stored in the TV Manager database and retained by normal source updates and database backups. Saved Network settings take precedence over the older `.env` `HOST` and `PORT` defaults. Imported SickChill `web_host`/`web_port` controls link to Network, making the effective configuration clear.

For temporary recovery, stop the app, open a fresh PowerShell in the installation directory, and run:

```powershell
.\run-prod.ps1 -ListenAddress 127.0.0.1 -Port 5050
```

These parameters set `TVMANAGER_BIND_HOST` / `TVMANAGER_BIND_PORT` for that PowerShell session. They override saved settings without changing them. Network shows that an override is active and prevents misleading saves. Close that PowerShell before a normal launch. To permanently recover a saved address after moving the server, use the all-interfaces address `0.0.0.0` in the existing installation before the move, or edit the saved Network settings from a working listener. If the saved address is already unavailable, use the following offline helper while TV Manager is stopped:

```powershell
.\.venv\Scripts\python.exe configure_network.py --host 127.0.0.1 --port 5050
```

Then launch normally and configure the new LAN address in Settings. The helper preserves other settings and does not disable login.

## A meaningful path to 100%

Launchpad replaces the old capped heuristic with **Installation readiness**. Seven automatic checks cover loaded library data, folder assignments, existing episode files, duplicate candidates, metadata IDs, metadata refresh and the active network configuration. Five operator checks record search/download, processing/media-server refresh, backup/recovery, restart/scheduling and single-manager cutover tests.

Expand each operator check, perform its test on the installed server, enter the result, confirm that it passed, and click **Record Verification**. Records are identified as operator verification, not automatic integration tests. They expire after 90 days and become stale after a new release or relevant saved configuration change. Clear a record to require verification again. All twelve checks must pass for 100%; the score does not certify full SickChill feature parity.

Missing-file and metadata field names now match Library Health. Duplicate totals cover all groups even when the displayed sample is limited. File checks honor the saved path mappings. Failed/incomplete health checks remain unverified, and wanted/unaired episodes with no file yet are not counted as missing existing files. Setup Assistant uses the same score. The separate package-file checklist is clearly labeled as installed-file checks.

## Update an existing Windows installation

Source: https://github.com/fpetillo/TV-Manager-Pro/tree/v18.11.0

ZIP: https://github.com/fpetillo/TV-Manager-Pro/archive/refs/tags/v18.11.0.zip

1. Finish active jobs, stop TV Manager and make a cold backup of the installation folder.
2. Extract the tagged ZIP elsewhere. Copy the **contents** of its TV-Manager-Pro-18.11.0 folder into the existing installation, allowing source-file replacement.
3. Preserve the existing database, `.env`, settings, backups, imports, recovery/runtime history and the server's working `.venv`. Do not nest the extracted folder inside the installation.
4. In PowerShell at the installation folder, run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\run-prod.ps1
```

5. Verify version 18.11.0, refresh the browser with Ctrl+F5, then configure Network as above.

## Validation and limits

Validation: 490 tests passed; two existing Windows symbolic-link tests skipped for account permission. All 71 top-level Python modules and 43 JavaScript assets pass syntax checks; dependency consistency and both PowerShell launcher parse checks pass. Isolated browser testing verified rejected unavailable addresses, saved/pending listener details, a real restart from localhost to the QA computer's LAN IP/port using Waitress, authenticated access, operator-record persistence, 100% with all fixture checks recorded, and 91% after clearing one check in both Launchpad and Setup Assistant. No browser console errors. The earlier test run found one obsolete source-location assertion; it was updated for the shared readiness module and the final full suite passed. Tests use isolated databases and application copies. No target-server configuration, firewall, real media, downloader or Plex operation is performed by this source release. A new Windows executable/installer is not included. Full SickChill parity and 100% readiness of the user's installed server remain unverified until its checks are completed.
