# TV Manager v17.3.3

Operator-visible SickChill import progress release.

## Added

- Background SickChill import jobs with a job ID and status endpoint.
- Import Center progress bar with stage, percent complete, status message, and live counters.
- Progress stages for analyze, source read, target write, show import, episode import, commit, verify, recovery, complete, and error.
- `POST /api/import/sickchill/jobs` to start an asynchronous import.
- `GET /api/import/sickchill/jobs/<job_id>` to poll import status.

## Improved

- Long imports no longer leave the operator staring at a frozen page.
- Import errors and database-lock failures now surface through the progress panel.
- Existing synchronous import API remains available for scripts and compatibility.
