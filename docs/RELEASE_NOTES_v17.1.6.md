# TV Manager v17.1.6

## Startup schema repair fix

This patch fixes startup failures when an existing `tvmanager.db` was created by an older build whose `shows` table did not yet include `imdb_id`.

### Fixed

- Adds `shows.imdb_id` during startup schema repair before creating the IMDb index.
- Allows older databases to launch and migrate cleanly instead of failing with `sqlite3.OperationalError: no such column: imdb_id`.
- Keeps About, Library Health, route diagnostics, and version endpoints from v17.1.5.

### Operator note

After installing, fully stop the old server process and restart from the extracted v17.1.6 folder. The first startup may upgrade the existing database schema.
