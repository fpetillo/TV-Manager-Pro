# Database Recovery and Safety

TV Manager performs a SQLite integrity check before it repairs or migrates the local database.

If startup reports `database disk image is malformed`, stop immediately. Do not keep starting the app against the same database because additional writes can make recovery harder.

## Windows recovery steps

```powershell
cd "C:\Acuityware TV Manager"

Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process -Force

New-Item -ItemType Directory -Force .\corrupt-db | Out-Null
Copy-Item .\tvmanager.db .\corrupt-db\tvmanager-malformed-$(Get-Date -Format yyyyMMdd-HHmmss).db -ErrorAction SilentlyContinue

Get-ChildItem . -Filter "tvmanager-before-*.db" | Sort-Object LastWriteTime -Descending | Select-Object LastWriteTime,Length,Name
Get-ChildItem .\backups -Filter "*.db" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object LastWriteTime,Length,Name
```

Pick the newest known-good backup, then restore it:

```powershell
Copy-Item ".\backups\YOUR-BACKUP-FILE.db" ".\tvmanager.db" -Force
.\run.ps1
```

## EXE build note

The Windows EXE build script sets `TVMANAGER_BUILDING_EXE=1` while PyInstaller analyzes the app. This prevents the build process from opening or repairing the live operator database.
