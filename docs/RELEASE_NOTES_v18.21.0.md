# TV Manager v18.21.0 — Faster verified update backup

Built on v18.20.0.

## What changed

Updating with `update-server.ps1` was slow because the "verified recovery backup" copied and SHA-256-checked almost the whole installation folder. That included runtime data the updater never changes: `managed_trash` (replaced video files), `imports`, `recovery`, `logs`, `diagnostics` and similar. It also copied the whole Python environment (`.venv`, thousands of small files) and reinstalled packages on every update.

The backup now covers what an update can change or a rollback needs, and nothing else:

| | Before | Now |
|---|---|---|
| Source, settings, `VERSION`, deployable folders | Copied and verified | Copied and verified (unchanged) |
| Database | File copy plus `-wal`/`-shm`, hashed twice, checked twice | SQLite backup (includes committed WAL changes), integrity-checked copy, one self-contained file |
| `managed_trash`, `imports`, `recovery`, `logs`, `diagnostics`, `uploads`, `archive-staging`, `rename-journals`, `corrupt-db`, `db-emergency` | Copied and verified | Left in place (the updater never writes them) |
| `*.log`, `*.zip` in the installation folder | Copied | Left in place |
| `.venv` and `pip install` | Every update | Only when the release's `requirements.txt` differs from the installed one (or with `-RefreshDependencies`) |
| Old update backups | Kept forever | Newest 5 completed backups kept (`-KeepBackups`, `0` keeps all) |

Rollback still restores every changed file from the verified backup, and restores `.venv` whenever packages were being changed. Backups from updates that rolled back or need manual recovery are never pruned. The nightly auto-updater passes `-KeepBackups 0` and keeps pruning with its own `keep_backups` setting.

Each update now prints the time taken per step (for example `backup files 0.1 s, backup database 1.7 s, install files 0.3 s`), and `update.json` records `timings_seconds`, `dependencies_changed`, `backup_scope` and `left_in_place`.

## Updating to 18.21.0

Download the new `update-server.ps1` from the v18.21.0 tag first, as in [WINDOWS_SERVER_UPDATE.md](WINDOWS_SERVER_UPDATE.md). The faster backup is in the script, so an older local copy would still take the slow path for this update.

## Validation

- 595 passed, 11 skipped on the Linux build host (Windows-only PowerShell, updater lock and service checks); the full suite also runs on GitHub's Windows runner.
- 12 new updater tests: runtime folders and logs left in place, every backed-up file matches its recorded hash, unchanged requirements skip pip and `.venv`, changed requirements back up `.venv` and run pip, `-RefreshDependencies`, rollback after a failed pip run and after a failed file install, committed WAL rows present in the database copy with no `-wal` file, corrupt database stops the update before any change, pruning keeps the newest completed backups and never removes rolled-back or manual-recovery backups, `-KeepBackups 0`.
- Timing on the build host, same fake installation (real 2,400-file Python environment, 1 GB `managed_trash`, 300 MB database, pip stood in by a 20 s pause): 49.6 s with the 18.20.0 updater, 2.5 s with 18.21.0. Windows antivirus scanning makes small-file copies slower, so the difference on the server should be larger.
- Not performed: an update on the Windows server.
