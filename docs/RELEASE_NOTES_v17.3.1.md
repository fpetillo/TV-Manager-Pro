# TV Manager v17.3.1

## Import visibility and database verification fix

This release fixes a real-world migration issue where SickChill analysis completed and import appeared to run, but the Shows screen displayed zero shows.

### Added

- Post-import active database verification.
- `GET /api/import/verify` support endpoint.
- Conservative `?recover=1` mode that can rebuild missing show rows from item-level import audit records if a previous import recorded audit detail but the `shows` table is empty.
- `diagnostics/last-import-verification.json` written after import/verification.
- Import Center now shows the active TV Manager database path plus live show/episode counts after import.
- Shows page now attempts a safe audit-based recovery when import history exists but no shows are visible.

### Safety

Recovery never deletes records. It only fills an empty `shows` table from existing SickChill import audit rows.
