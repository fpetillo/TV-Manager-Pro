# TV Manager v18.2.4 — No-Hang Show Detail Hotfix

This hotfix removes the remaining first-load wait from Show Detail. The page now renders show information, seasons, and episodes independently so expensive counts or background scans cannot leave the operator staring at an indeterminate loading bar.

## Highlights

- New fast seasons endpoint: `GET /api/shows/<id>/seasons-fast`
- Show header no longer waits for season count aggregation.
- Detailed season counts refresh in the background.
- Episode list uses lean columns and a shorter first-page timeout.
- UI failures show retry, Jobs, and Logs links instead of hanging.
- `app.py` fallback server now runs threaded with debug disabled.
- Read-only SQLite UI requests use a shorter busy timeout so blocked reads fail fast.

## Validation

- Python compile check
- JavaScript syntax check
- Targeted v18.2.4 regression checks
