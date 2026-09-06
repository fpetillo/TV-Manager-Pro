# TV Manager v17.1 Release Notes

TV Manager v17.1 turns the v17 migration-hardening foundation into an operator-facing workflow.

## Highlights

- **Import Center UI** — SickChill database migration now follows a guided Analyze → Preview → Import flow. Analyze and Preview do not write TV Manager records.
- **Post-import Library Health** — new `/library-health` page and `/api/library/health-report` endpoint show missing episode files, missing IDs, shows without locations, metadata refresh gaps, duplicate candidates, and recommendations.
- **Safe duplicate cleanup** — new preview/apply API moves only explicitly previewed files to `managed_trash`; it never deletes directly. Every apply attempt is written to `duplicate_cleanup_actions`.
- **Dashboard integration** — the main dashboard now surfaces missing-file and duplicate-group counts with a direct Library Health link.

## New endpoints

- `GET /library-health`
- `GET /api/library/health-report`
- `POST /api/library/duplicates/preview`
- `POST /api/library/duplicates/apply`

## Validation

- Full unit test suite passes locally.
- New tests cover v17.1 route contracts, library health reporting, and managed-trash duplicate cleanup behavior.
