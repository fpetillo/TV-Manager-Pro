# TV Manager v18.14.0 — Automatic deployment on the Windows server

Built on v18.13.0. Source release.

## Unattended running and nightly updates

- **install-auto-deploy.ps1** (run once as Administrator on the server) registers two scheduled tasks under the Windows account you choose, so UNC media shares keep working:
  - **TV Manager Production** starts TV Manager at boot without anyone signed in.
  - **TV Manager Auto Update** runs nightly (default 03:30).
  It disables the older sign-in task, starts TV Manager, confirms it answers and checks GitHub once. `-UpdateTime`, `-NoAutoUpdate` and `-Uninstall` are available.
- **start-production.ps1** takes the same startup database snapshot and runs the same schema check as run.ps1, then runs the server in its stoppable mode (`server.py --service`). It refuses to start while an update holds the maintenance flag. If the database check fails, startup stays blocked (`.runtime/startup-blocked.json`) so restart-on-failure cannot loop.
- **auto-update.ps1 / auto_update.py** install the newest `vX.Y.Z` tag when it is newer than VERSION:
  1. Wait for active jobs to finish (up to 2 hours, otherwise defer).
  2. Stop gracefully.
  3. Run update-server.ps1, which makes a verified backup and rolls back on its own failures.
  4. Start and confirm the new version answers.
  5. If it does not, restore source, `.venv` and database from the backup and start the previous version.

  Results go to `logs/auto-update.log` and `.runtime/auto-update-status.json`. `-Check` reports without changing anything. Setting `"enabled": false` in `auto_update.json` pauses updates. The 5 newest successful-update backups are kept.
- **New endpoint:** `GET /api/maintenance/activity` reports active job counts to the local updater. It answers only with the one-time token the updater writes into the installation's `.runtime` folder, and works whether or not browser login is on.
- `.runtime/` and `auto_update.json` are now git-ignored local state.

Setup guide: [AUTO_DEPLOY.md](AUTO_DEPLOY.md).

## Validation

- pytest: 539 passed, 11 skipped (Windows-only PowerShell, updater-lease and service checks on the Linux build host).
- 15 new tests (14 simulate the startup task, process, GitHub and updater. They cover: up-to-date, check-only, a full update after waiting for jobs, deferral when busy, updater failure, rollback after a failed start (source, `.venv` and database restored, failed files set aside), stop timeout with no file changes, not-running, disabled, concurrent runs, GitHub failure, backup pruning, the token-gated endpoint and the script wiring; 1 guards against Windows PowerShell 5.1 param-default path failures).
- End-to-end on a real TV Manager process (Linux; Task Scheduler and the PowerShell updater substituted): token-gated idle check, wrong token rejected, graceful stop in about 3 seconds, update, restart, new version confirmed, `updated` recorded, no flag or token left behind.
- All four PowerShell scripts parse under PowerShell 7.5. They were not executed on Windows: scheduled-task registration, boot start, account rights and real share access must be confirmed during setup on the server.
- 73 Python modules parse and 43 JavaScript files pass syntax checks.

## Activation

Follow [AUTO_DEPLOY.md](AUTO_DEPLOY.md): install 18.14.0 with update-server.ps1 while TV Manager is stopped, then run install-auto-deploy.ps1 as Administrator. Afterwards, each new version tag pushed to GitHub is installed the following night. No production server was changed.
