# TV Manager Database Protection Center

TV Manager v17.14.0 adds a professional database/config protection layer so the application is safer to upgrade, package, repair, import into, and operate with large libraries.

## What changed

- Startup creates a verified SQLite backup before schema repair when `tvmanager.db` exists.
- Backups use Python/SQLite's online backup API instead of raw hot-file copy.
- Every safe database backup is checked with `PRAGMA quick_check`.
- Backup records are written to `backups/db-backup-manifest.json`.
- `.env` is backed up as a redacted config snapshot by default.
- A new Database Safety Center lists database status, backup inventory, and newest usable backup.

## New page

Open:

```text
http://127.0.0.1:5050/database-safety
```

## New APIs

```text
GET  /api/protection/status
POST /api/protection/backup
GET  /api/protection/backups
GET  /api/jobs
GET  /api/jobs/<job_id>
```

## Command-line protection

```powershell
cd "C:\Acuityware TV Manager"
.\.venv\Scripts\python.exe protect_db.py --backup --reason manual
.\.venv\Scripts\python.exe protect_db.py --scan
```

## Backup locations

```text
backups/safe/       verified SQLite database backups
backups/config/     redacted config snapshots
backups/db-backup-manifest.json
```

## Why this matters

SQLite WAL mode is fast and reliable, but copying `tvmanager.db` while the app is running can produce incomplete backups if WAL/SHM state is not captured correctly. The SQLite backup API creates a consistent database image and then TV Manager verifies the backup before considering it usable.
