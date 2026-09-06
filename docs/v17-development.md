# TV Manager v17.0 Development Track

Branch: `v17.0-dev`

This branch contains the full v17.0 source tree for TV Manager.

## Local build status

The v17.0 source package was generated from the validated v16.0 package and tested locally.

- Test result: 44/44 passing
- Package: `imdb-tv-manager-v17.0.zip`
- SHA-256: `f0ca2f9d9a4a16377c0131d38791bda8f6b3b15c58a62dcbc8bd606299da80b6`

## v17.0 scope started

- SickChill no-write import analysis endpoint: `POST /api/import/sickchill/analyze`
- SickChill dry-run import preview endpoint: `POST /api/import/sickchill/preview`
- Idempotent SickChill importer with IMDb normalization and duplicate-safe repeat imports
- Legacy source identity tracking through `legacy_identity_map`
- Per-item import audit trail through `import_run_details`
- Duplicate-candidate API using the media fingerprint cache: `GET /api/library/duplicates`
- Manual bounded metadata refresh endpoint: `POST /api/metadata/refresh/run`
- v17 release notes and roadmap updates

## Next development targets

1. Wire the new analyze/preview/import flow into the Import UI.
2. Expand SickChill schema coverage using real-world database backups.
3. Add a post-import health report: missing paths, missing IDs, skipped episodes, and duplicate candidates.
4. Add safe duplicate cleanup workflow with preview/apply/rollback.
5. Prepare MSI installer and first-run wizard planning for v18.

## Important note

This branch now tracks the unpacked source tree directly. Generated runtime artifacts such as SQLite databases, logs, virtual environments, session keys, caches, and packaged zip archives are intentionally excluded from Git.
