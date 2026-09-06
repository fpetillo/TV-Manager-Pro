# TV Manager v17.0 Release Notes

TV Manager v17.0 begins the migration-hardening track. The goal is to make real SickChill migrations safer, repeatable, and easier to explain before automation is armed.

## Highlights

- **SickChill import analysis / no-write SickChill analysis** — upload a SickChill/SickBeard database and inspect detected tables, columns, counts, warnings, and sample shows before importing.
- **Dry-run import preview** — run the full matching/import decision engine without writing to `tvmanager.db`.
- **Idempotent importer** — repeat imports match existing shows by IMDb, TVDb, legacy indexer ID, or normalized show name, and duplicate episodes are skipped.
- **Legacy identity map** — the new `legacy_identity_map` table preserves source show IDs and their mapped TV Manager show IDs.
- **Per-item audit trail** — `import_run_details` records imported/skipped decisions for shows and episodes.
- **Duplicate candidate API** — `/api/library/duplicates` reports likely duplicate media files from the fingerprint cache.
- **Manual metadata refresh run** — `/api/metadata/refresh/run` allows a bounded operator-triggered refresh batch.

## Upgrade notes

Keep your existing `.env` and `tvmanager.db`. Run `setup.ps1` if dependencies are missing, then run `validate-release.ps1`. Schema updates are additive.

The v17 importer keeps the existing `/api/import/sickchill` endpoint but adds two safer preflight endpoints:

- `POST /api/import/sickchill/analyze`
- `POST /api/import/sickchill/preview`

Use preview first when testing against a live SickChill database backup.
