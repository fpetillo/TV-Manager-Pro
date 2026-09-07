# TV Manager v17.1.7

This patch continues the startup repair introduced for `no such column: imdb_id` and fixes startup against older existing `tvmanager.db` files where the `episodes` table did not yet include newer operational columns.

## Fixed

- Repairs missing `episodes.status` before `engine.normalize_statuses()` runs.
- Repairs missing `episodes.location`, `name`, `airdate`, `file_size`, `release_name`, `quality`, and `legacy_data`.
- Expands startup repair for older `shows` schemas as well.
- Keeps About, Library Health, route diagnostics, and version endpoints from the v17.1 series.

## Operator note

Install this over the existing folder, keep your existing `tvmanager.db`, and restart with `run.ps1`. The first startup may upgrade the database schema in place.
