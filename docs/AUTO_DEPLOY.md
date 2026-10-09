# Automatic deployment on the Windows server

From v18.14.0 a source installation can run without anyone signed in and install new
releases on its own. Once set up, **pushing a new version tag to GitHub is the
deployment**: the server picks it up at the next nightly check.

## What gets installed

| Scheduled task | Runs | What it does |
|---|---|---|
| **TV Manager Production** | At boot (1-minute delay), as your Windows account | `start-production.ps1`: startup database snapshot, schema check, then the server in stoppable mode (`server.py --service`). Restarts on failure. |
| **TV Manager Auto Update** | Daily, default 03:30 | `auto-update.ps1` → `auto_update.py`: installs a newer release, or does nothing. |

Both run as the account you enter during setup, so UNC library paths such as
`\\192.168.1.221\Media` work exactly as they do for you. Your password goes to Windows
Task Scheduler only.

## One-time setup on 192.168.1.11

1. **Get 18.17.0 onto the server.** Close the TV Manager window (Ctrl+C in the
   `run.ps1` window) and wait for it to exit. In PowerShell:

   ```powershell
   $Updater = "$env:TEMP\Update-TVManager.ps1"
   Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/fpetillo/TV-Manager-Pro/v18.17.0/update-server.ps1' -OutFile $Updater
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Updater -InstallDir 'C:\Acuityware TV Manager' -Version '18.17.0'
   ```

   Do not start TV Manager afterwards; the next step does that.

2. **Set up the tasks.** Open PowerShell **as Administrator**:

   ```powershell
   Set-Location 'C:\Acuityware TV Manager'
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install-auto-deploy.ps1
   ```

   Enter the Windows account that can open your media shares and its Windows password
   (not a Hello PIN). The script registers both tasks and disables the older sign-in
   task `TV Manager` if present. It then starts TV Manager through the startup task,
   confirms it answers, and checks GitHub once without changing anything.

3. **Confirm.** Open `http://192.168.1.11:5050`, check About shows 18.17.0, then reboot
   the server once and confirm TV Manager comes back before anyone signs in.

Use `-UpdateTime 02:00` to pick another check time, `-NoAutoUpdate` for unattended
startup only, and `-Uninstall` to remove both tasks.

## What a nightly run does

1. Reads the version tags on GitHub and compares the newest `vX.Y.Z` with `VERSION`.
   If it is not newer, it records `up_to_date` and stops.
2. Waits until TV Manager reports no active jobs, checking every 5 minutes for up to
   2 hours. If it is still busy, the run is deferred to the next night (`deferred_busy`).
3. Sets a maintenance flag, which makes the startup task refuse to start, then asks TV
   Manager to stop. The server refuses new requests, finishes active work (up to 150
   seconds) and exits.
4. Runs `update-server.ps1` for that version. It verifies the release archive, makes a
   full recovery backup (source, database, settings, `.venv`), installs dependencies and
   source, and restores everything itself if any of that fails.
5. Starts the task and waits up to 25 minutes (startup runs the database snapshot and
   check first) for `/api/version` to report the new version.
6. If the new version does not come up, it stops it and restores source, `.venv` and the
   database from the recovery backup. The new version's database and files are kept in
   the backup's `failed-start` folder for review. It then starts the previous version
   and records `rolled_back`.

Only one run happens at a time. Successful updates keep the 5 newest recovery backups
next to the installation (`C:\Acuityware TV Manager Update Backups`); failed and
rolled-back backups are never removed automatically.

## Day to day

| To… | Run (in the installation folder) |
|---|---|
| See what would happen | `.\auto-update.ps1 -Check` |
| Update right now | `.\auto-update.ps1` |
| Install a specific newer version | `.\auto-update.ps1 -Version 18.17.0` |
| Pause automatic updates | Set `"enabled": false` in `auto_update.json` |
| Stop TV Manager | `.\.venv\Scripts\python.exe server.py --stop-service` |
| Start TV Manager | `Start-ScheduledTask -TaskName 'TV Manager Production'` |

Results are in `logs\auto-update.log` (one line per step) and
`.runtime\auto-update-status.json`. The `result` field is one of `updated`,
`up_to_date`, `deferred_busy`, `update_failed`, `rolled_back`, `stop_timeout`,
`disabled` or `error`. Startup messages are in `logs\startup.log`, and server console
output is in `logs\server.out.log` / `server.err.log`.

`auto_update.json` settings: `enabled`, `repository`, `production_task`,
`max_wait_minutes` (120), `busy_poll_minutes` (5), `stop_timeout_seconds` (240),
`start_timeout_seconds` (1500), `keep_backups` (5).

## Things to know

- **A tag is a deployment.** Push a version tag only when you want it on the server that
  night. Downgrades are never installed.
- **Start TV Manager only through the startup task** after setup. A copy started by hand
  with `run.ps1` cannot be stopped by the updater; the update then fails safely and
  retries the next night.
- If the database check fails at startup, TV Manager stays stopped and
  `.runtime\startup-blocked.json` explains why. Fix or restore the database, delete that
  file, then start the task.
- This covers source installations. The packaged service ZIP (v18.12.0 `TVManagerService`)
  has its own upgrade steps; see [WINDOWS_SERVICE.md](WINDOWS_SERVICE.md).
