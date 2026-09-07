# TV Manager v17.15.0 Background Jobs and Scheduler

TV Manager now treats long-running work as background jobs so the operator can start work, switch pages, and keep using the application while the process continues.

## Background job center

Open:

```text
/jobs
```

The Active Jobs screen displays recent and running jobs with progress bars, stage, message, processed/total counts, success/failure counters, current show, and recent errors.

Shared job APIs:

```text
GET /api/jobs
GET /api/jobs/<job_id>
```

## Long-running actions now support progress

The following workflows can run in background/job mode:

- Episode search
- Recent search
- Backlog search
- Scheduler manual run
- Show metadata refresh
- Missing metadata refresh
- Show/episode artwork refresh
- Post-processing
- Library Health scan
- Database/config protection
- Full-library metadata refresh
- SickChill import jobs

## Scheduler additions

The scheduler now includes SickChill-style maintenance jobs beyond recent/backlog search:

- `missing_metadata`
- `artwork_refresh`
- `library_health_scan`
- `database_protection`

These jobs are visible in Settings -> Automation and can be enabled/disabled or run manually.

## Metadata and art

Episode metadata now stores richer TMDb fields when available:

- `overview`
- `still_url`
- `still_path`
- `tmdb_episode_id`
- `metadata_updated_at`

This supports episode art and better missing-metadata maintenance.

## Safety

Database/config protection remains separate from raw file copies. Use Database Safety Center for verified SQLite backups and redacted config snapshots before major imports, metadata refreshes, upgrades, or recovery work.
