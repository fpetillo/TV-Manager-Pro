# TV Manager — Fresh Windows PC Installation

This is the canonical procedure for installing TV Manager on a new Windows 10/11 PC.

## 1. Prerequisites

Install a current 64-bit Python release. Python 3.12 or 3.13 is recommended.

During Python installation, enable:

- **Add python.exe to PATH**
- **Install launcher for all users** if offered

Verify from a new PowerShell window:

```powershell
py --version
python --version
```

At least one of those commands should report Python successfully.

## 2. Create the TV Manager folder

Recommended location:

```text
C:\Acuityware TV Manager
```

Extract the TV Manager release ZIP so files such as these are directly inside that folder:

```text
C:\Acuityware TV Manager\app.py
C:\Acuityware TV Manager\setup.ps1
C:\Acuityware TV Manager\run.ps1
C:\Acuityware TV Manager\run-prod.ps1
C:\Acuityware TV Manager\requirements.txt
```

Avoid an accidental nested path such as:

```text
C:\Acuityware TV Manager\imdb-tv-manager-v15.0\imdb-tv-manager-v15.0\
```

## 3. Allow PowerShell scripts

Recommended persistent setting for the current Windows user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Answer `Y` if PowerShell asks for confirmation.

If you only want to allow scripts in the current PowerShell window:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

You must repeat the `Process` version each time a new PowerShell window is opened.

Check the active policies with:

```powershell
Get-ExecutionPolicy -List
```

## 4. Open PowerShell in the TV Manager folder

```powershell
cd "C:\Acuityware TV Manager"
```

## 5. Run the setup script

```powershell
.\setup.ps1
```

The setup script:

1. Creates `.venv` if it does not already exist.
2. Activates the virtual environment.
3. Updates `pip`.
4. Installs everything in `requirements.txt`.
5. Installs Flask, Requests, python-dotenv, and Waitress.
6. Creates `.env` from `.env.example` if `.env` does not already exist.

Waitress is required for `run-prod.ps1`.

To manually repair or refresh all dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

To install Waitress alone if needed:

```powershell
.\.venv\Scripts\python.exe -m pip install waitress==3.0.2
```

Verify Waitress:

```powershell
.\.venv\Scripts\python.exe -c "import waitress; print('Waitress OK')"
```

Expected result:

```text
Waitress OK
```

## 6. Configure `.env`

Open:

```text
C:\Acuityware TV Manager\.env
```

At minimum configure the TMDb bearer token used for show metadata/search.

Typical values:

```text
TMDB_BEARER_TOKEN=your_tmdb_token_here
PORT=5050
```

The default application binding is localhost for safety.

Do not commit `.env` to GitHub.

## 7. First startup

For initial testing:

```powershell
.\run.ps1
```

Open:

```text
http://127.0.0.1:5050
```

The Flask development runner is useful while validating a new installation or upgrade.

## 8. Production startup

After the application is working correctly:

```powershell
.\run-prod.ps1
```

This starts TV Manager using Waitress.

Default production URL:

```text
http://127.0.0.1:5050
```

Check status from another PowerShell window:

```powershell
.\status.ps1
```

## 9. Start TV Manager automatically

After validating `run-prod.ps1`:

```powershell
.\install-production-startup.ps1
```

This creates a Windows Scheduled Task named:

```text
TV Manager Production
```

The task starts TV Manager at logon and is configured to restart after failures.

If an older `TV Manager` startup task also exists, disable or remove the older task so only one web-server instance starts.

Scheduler leases protect automation jobs from duplicate execution, but two web servers cannot bind to the same TCP port.

## 10. Moving an existing TV Manager installation to another PC

For a migration from an existing TV Manager PC, preserve these items:

```text
tvmanager.db
.env
```

Also preserve any local files/directories you intentionally use, such as custom configuration or mappings.

Recommended procedure:

1. Stop TV Manager on the old PC.
2. Make a safe copy of `tvmanager.db` and `.env`.
3. Install the same or newer TV Manager release on the new PC.
4. Run `setup.ps1` on the new PC.
5. Stop TV Manager if it started.
6. Copy the existing `tvmanager.db` and `.env` into the new TV Manager folder.
7. Start with `run.ps1` first.
8. Confirm Dashboard, Shows, Settings, download clients, paths, and Post Processing.
9. Use **Post Processing → Preview Naming & Import** before enabling automatic processing.
10. Move to `run-prod.ps1` only after validation.

TV Manager performs versioned database migrations and creates migration backups, but keep your own copy before moving to another machine.

## 11. Existing SickChill migration

If moving from SickChill rather than another TV Manager installation:

1. Complete the fresh TV Manager setup.
2. Start TV Manager.
3. Open **Migration**.
4. Import the SickChill SQLite database.
5. Import the SickChill `config.ini`.
6. Review Settings, Download Clients, Providers, Quality, library roots, and naming configuration.
7. Use Post Processing preview before allowing live file moves.

Do not place SickChill `config.ini` in GitHub. It may contain credentials and API keys.

## 12. Network paths and UNC shares

If TV Manager accesses paths such as:

```text
\\SERVER\TV
\\NAS\Downloads
```

the Windows account running TV Manager must have permission to those shares.

A Scheduled Task running under a different Windows account may not see the same mapped drive letters as your interactive desktop session.

Prefer UNC paths over mapped drive letters for always-on operation.

Example:

```text
\\192.168.1.221\Downloads\Complete
```

Use **Operations → Root & Path Health** to verify paths from TV Manager.

## 13. Windows Firewall / LAN use

TV Manager binds to `127.0.0.1` by default, which means only the local PC can access it.

Do not change the host binding merely to make TV Manager Internet-accessible.

LAN/browser authentication and CSRF hardening remain separate security controls. If LAN access is enabled later, restrict it to trusted networks and use an appropriate firewall rule/reverse proxy.

## 14. Common problems

### PowerShell says scripts are disabled

For the current session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Or persist the normal user setting:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### `run-prod.ps1` fails while importing Waitress

Install all required packages:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Verify:

```powershell
.\.venv\Scripts\python.exe -c "import waitress; print('Waitress OK')"
```

### Virtual environment is missing

Run:

```powershell
.\setup.ps1
```

### `python` or `py` is not recognized

Install Python and reopen PowerShell. Make sure Python was added to PATH.

### Port 5050 is already in use

Check whether another TV Manager instance is already running:

```powershell
Get-NetTCPConnection -LocalPort 5050 -ErrorAction SilentlyContinue
```

Check Python processes:

```powershell
Get-Process python -ErrorAction SilentlyContinue
```

Do not run `run.ps1` and `run-prod.ps1` at the same time.

### TV Manager starts but cannot see network folders

Confirm:

- the UNC path is reachable;
- the Windows account has share and NTFS permissions;
- the Scheduled Task runs under the expected account;
- mapped drive letters are not being relied upon by a background task.

Use **Operations → Root & Path Health**.

### Production startup task exists but application is not reachable

Run interactively first:

```powershell
.\run-prod.ps1
```

Then:

```powershell
.\status.ps1
```

Check Windows Task Scheduler history and confirm another process is not already using port 5050.

## 15. Upgrade procedure on an existing TV Manager PC

Before upgrading:

1. Stop TV Manager.
2. Back up `tvmanager.db`.
3. Back up `.env`.
4. Extract the new application files.
5. Keep your existing database and `.env`.
6. Run:

```powershell
.\setup.ps1
```

This refreshes dependencies for the new release.

Then test:

```powershell
.\run.ps1
```

Once validated:

```powershell
.\run-prod.ps1
```

Do not replace your existing `tvmanager.db` with a database from a release ZIP. Official TV Manager release ZIPs do not contain a runtime database.

## 16. Files that must never be committed to GitHub

The repository `.gitignore` protects these, but always verify before committing:

```text
.env
config.ini
tvmanager.db
tvmanager.db-wal
tvmanager.db-shm
backups/
logs/
diagnostics/
managed_trash/
__pycache__/
```

` .env.example ` is safe to commit because it contains placeholders rather than live credentials.


## 17. Enable access from another PC on the LAN

First verify TV Manager locally:

```powershell
.\run-prod.ps1
```

Open:

```text
http://127.0.0.1:5050
```

Then create browser credentials:

```text
http://127.0.0.1:5050/security/setup
```

or open **Settings → Security**.

Create a 12+ character password and enable **Require browser login**.

Stop TV Manager and add this to `.env`:

```text
HOST=0.0.0.0
PORT=5050
```

Start again:

```powershell
.\run-prod.ps1
```

v16 will refuse `HOST=0.0.0.0` unless browser authentication is configured and enabled.

If Windows Firewall blocks the port, an administrator can add a private-network rule:

```powershell
New-NetFirewallRule -DisplayName "TV Manager 5050" -Direction Inbound -Protocol TCP -LocalPort 5050 -Action Allow -Profile Private
```

Use the TV Manager PC's LAN address from the second PC, for example:

```text
http://192.168.1.50:5050
```

Keep the firewall profile restricted to `Private`. Do not open the port to the public Internet.

To remove the rule later:

```powershell
Remove-NetFirewallRule -DisplayName "TV Manager 5050"
```
