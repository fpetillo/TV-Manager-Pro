# Update an existing Windows server

Use `update-server.ps1` for an existing **source installation** with a working `.venv` Python environment. Git is not required. It defaults to `C:\Acuityware TV Manager` and release **18.11.2**. Run it on the server being updated, using an account with access to the installation and its parent folder. This does not update a packaged `TVManager.exe` installation.

## Run the update

1. Finish active jobs and stop TV Manager. If you use a startup task or Windows service, stop it and prevent automatic restarts during the update. The updater leaves its configuration unchanged.
2. Open PowerShell **on the server**, then paste:

```powershell
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$Updater = Join-Path $env:USERPROFILE 'Downloads\Update-TVManager.ps1'
Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/fpetillo/TV-Manager-Pro/v18.11.2/update-server.ps1' -OutFile $Updater
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Updater -InstallDir 'C:\Acuityware TV Manager'
```

Change only `-InstallDir` if your installation is elsewhere. Execution-policy bypass applies only to this PowerShell process. The script downloads the tagged official source ZIP and reports errors instead of continuing a failed update.

3. Wait for **Updated source to v18.11.2. TV Manager remains stopped.** If it reports any error, keep TV Manager stopped and review the error and recovery folder before retrying.
4. Restart with your existing task/service, or run the following for a manual production session. Use one startup method:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\Acuityware TV Manager\run-prod.ps1'
```

5. Open TV Manager, verify **18.11.2** in About, and press **Ctrl+F5**. Source installation and successful server startup are separate checks.

If Downloads does not exist under your Windows account, save the script to another folder and change `$Updater` accordingly. If permissions block the installation or backup folder, use an account permitted to maintain that installation.

## Set the server address

The release includes **Settings â†’ Network**. If the app is still listening locally, open `http://127.0.0.1:5050` on the server. Configure an administrator password and require browser login in **Settings â†’ Security** if needed. Then save `192.168.1.11` and port `5050` in Network and restart normally. That address must belong to the server. The updater preserves your current address; it does not guess or change it.

See [Network setup and firewall guidance](RELEASE_NOTES_v18.11.0.md) for LAN access and offline address recovery. The updater does not modify firewall rules.

## Backups and failures

For the default installation, backups go to:

```text
C:\Acuityware TV Manager Update Backups\<timestamp>-v<old-version>-<unique-id>\
```

Each backup includes the installation's source, database and SQLite sidecars, `.env`, session key, configuration, imports, recovery state and `.venv`, with SHA-256 verification of copied files and SQLite checks. Previously stored `backups`, `.git`, `.runtime`, Python/test caches and lock files are excluded and remain in place. Media outside the installation is untouched and is not copied. If you store media inside the installation, that content is included in the backup and needs sufficient free space. Linked/junction paths require a manual update; the script stops before changing source.

The script takes the application's installation lock and refuses to update a running instance. It checks the archive layout, version, manifest, Python syntax, destination paths, database and free space before changing source or dependencies. It never imports the app, launches a scheduler or runs database migrations. Normal startup performs the existing database protection and migrations.

Dependency installation and consistency checks must pass before copying source. On a caught dependency or copy error, it attempts to restore changed source and the backed-up Python environment. It leaves database and settings in place and returns a failure status. `update.json` records progress and hashes; `RESTORE.txt` explains recovery. Power loss, forced termination or a failed rollback can still require manual recovery. Keep the app stopped until recovery is complete. Restore `.venv` at its original installation path. Do not overlay an old database on newer WAL/SHM files or roll back after production resumes without reviewing newer work.

Keep the backup folder private: it contains your existing settings and credentials. Do not upload it to GitHub.

For an already downloaded **official tagged source ZIP**, use:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Update-TVManager.ps1 -InstallDir 'C:\Acuityware TV Manager' -Version '18.11.2' -ArchivePath 'C:\Downloads\TV-Manager-Pro-18.11.2.zip'
```

Dependencies may still need an internet connection. `-Version` can select a newer tagged release; downgrades are refused. Archive hashes in the backup journal identify the downloaded file, not an independently signed release.
