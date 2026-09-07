# TV Manager v17.3.2 Release Notes

## Focus

This release fixes the SickChill import path when SQLite reports `database is locked` after import and the Shows page remains empty.

## Fixes

- Reworked the SickChill importer transaction flow.
- Reads the SickChill source database into memory and closes that connection before writing TV Manager data.
- Repairs/verifies the target `tvmanager.db` schema before import writes begin.
- Uses an explicit `BEGIN IMMEDIATE` target transaction with clear commit/rollback/finally close behavior.
- Runs post-import visibility verification only after the writer connection is closed.
- Returns committed target counts in `target_visibility`.
- Adds retry protection around the app-level post-import verification.

## Validation

- 86/86 automated tests passing.
- Python compile check passed.
- Regression coverage confirms the database is writable immediately after import and imported shows/episodes are visible from a fresh connection.
