# Release Notes — v18.2.0

## Bulk Episode Management & Ignore Rules

This release adds a SickChill-style episode management layer focused on professional bulk operations and precise wanted/missing-count control.

### Highlights

- Added episode-level ignored/not-considered flag.
- Added ignored reason, ignored timestamp, ignored source, and management note fields.
- Added bulk episode controls on Show Detail.
- Added Season 00 / Specials ignore/include actions per show.
- Added Manage page filters for Specials-only and Ignored-only episode operations.
- Added ability to ignore/include all matching episodes from Manage.
- Disabled direct searching for ignored episodes.
- Excluded ignored episodes from Show Queue counts and missing episode display.
- Excluded ignored episodes from recent/backlog search eligibility.
- Added episode management history tracking.

### New APIs

```text
POST /api/episodes/bulk/preview
POST /api/episodes/bulk/apply/start
POST /api/shows/<show_id>/specials/ignore/start
POST /api/shows/<show_id>/specials/include/start
```

### Validation

- Full pytest suite passes.
- Python compile check passes.
- JavaScript syntax check passes.
- Package hygiene excludes database, environment, logs, diagnostics, caches, build output, and generated archives.
