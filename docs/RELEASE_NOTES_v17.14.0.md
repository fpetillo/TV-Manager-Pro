# TV Manager v17.14.0 — Database Protection + Progress Polish

This release begins the professional polish pass needed for wider distribution.

## Highlights

- Added `database_safety.py` for verified SQLite database backups.
- Added `protect_db.py` command-line tool for backup/status scans.
- Added Database Safety Center at `/database-safety`.
- Startup now creates a verified pre-startup backup before schema repair when possible.
- Configuration files are backed up with `.env` secrets redacted by default.
- Added backup manifest tracking and SHA-256 checksums.
- Added shared `job_center.py` progress-job registry.
- Library Health now runs as a progress job with a progress bar.
- Added shared job APIs for future progress-driven operations.
- Added protection status to Library Health recommendations.

## New APIs

```text
GET  /api/jobs
GET  /api/jobs/<job_id>
GET  /api/protection/status
POST /api/protection/backup
GET  /api/protection/backups
POST /api/library/health-scan/start
GET  /api/library/health-scan/jobs/<job_id>
```

## Notes

This release does not replace a malformed database automatically. It makes backups safer going forward and gives the operator a cleaner place to verify, scan, and protect database/config state.
