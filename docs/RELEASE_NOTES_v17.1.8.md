# TV Manager v17.1.8

Startup database-doctor build.

## Fixes

- Adds `db_doctor.py`, an idempotent startup schema repair tool for older local `tvmanager.db` files.
- Runs database repair before Flask, engine, migrations, indexes, and route registration depend on newer columns.
- Updates `run.ps1` to display the running version/folder and run the database repair step before launching the app.
- Writes `diagnostics/startup-db-repair.json` so support can see exactly which columns were added.
- Backfills blank show/episode statuses to `Wanted`.

## Targeted failures

- `sqlite3.OperationalError: no such column: imdb_id`
- `sqlite3.OperationalError: no such column: status`
- Similar old-database startup failures caused by missing required columns.

## Upgrade note

The first startup may upgrade an older local database. `run.ps1` now performs the repair before launching the Flask app.
