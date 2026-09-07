# Downloader Validation Center

TV Manager v17.19.0 adds a dedicated downloader validation and monitoring surface at `/download-center`.

## Purpose

The Download Center confirms that the search-to-download handoff is actually working before cutover from SickChill. It is designed for operator confidence:

- confirm which downloader clients are selected and configured without exposing secrets;
- run downloader connection tests as background jobs with progress;
- poll active downloader queues as background jobs;
- view recent local download records and external IDs;
- view accepted search results that are ready to send to the configured client;
- send a result to the downloader and monitor the handoff job;
- review recent downloader-related events and jump to the full Logs screen.

## Pages

- `/download-center` — downloader readiness, connection tests, handoff candidates, and queue monitor.
- `/queue` — acquisition queue/history view.
- `/jobs` — background job progress.
- `/logs` — searchable/sortable log events.

## APIs

- `GET /api/downloaders/monitor`
- `GET /api/downloaders/readiness`
- `POST /api/downloaders/test/start`
- `POST /api/downloaders/poll/start`
- `POST /api/downloads/monitor/start`
- `POST /api/search-results/<id>/grab/start`

## Launchpad readiness

The Launchpad text "replacement readiness" is a calculated cutover score. It does not download anything by itself. It summarizes whether TV Manager has visible shows, library-health blockers, metadata gaps, downloader configuration, and operator actions still needing attention.

If Launchpad stays on a loading message, the readiness API did not return successfully. v17.19.0 now shows a clear failure message and points the operator to `/api/launchpad/summary` and Logs.
