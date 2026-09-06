# TV Manager 13.0.1 Hotfix

This hotfix corrects a startup failure introduced in v13.0 where one or more modules referenced the centralized `dbcore` database helper without importing it.

## Fixed
- `production.py` now imports `dbcore` before calling `dbcore.connect(...)`.
- All top-level Python modules are audited for `dbcore.` usage without a corresponding import.
- Version metadata updated to 13.0.1.

## Upgrade
Replace the application files with v13.0.1 while preserving your existing `tvmanager.db`, configuration, backups, and `.env`.
