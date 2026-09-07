# TV Manager v17.13.2 - Windows EXE Build + Database Safety Patch

This patch hardens Windows packaging and startup behavior after a malformed SQLite database was encountered during the EXE build/startup workflow.

## Fixed

- `installer/windows/build-exe.ps1` now sets `TVMANAGER_BUILDING_EXE=1` during PyInstaller analysis so packaging does not touch the live `tvmanager.db`.
- Startup database repair now performs a SQLite `PRAGMA quick_check` before attempting schema writes.
- Malformed/corrupt databases now stop startup with a clear recovery message instead of a raw traceback.
- `run.ps1` now uses the project virtual environment Python consistently and stops before importing `app.py` if the database safety check fails.

## Added

- `docs/DATABASE_RECOVERY.md` with Windows recovery steps for `database disk image is malformed`.

## Operator impact

The EXE build can now proceed even if an existing local `tvmanager.db` needs recovery, because packaging no longer opens the live database. Runtime startup still protects the database and requires restore from a known-good backup when SQLite reports corruption.
