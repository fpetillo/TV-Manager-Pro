# TV Manager v17.18.0 — Progress Everywhere + Professional Logs

This release continues the professional distribution polish pass and addresses the operator requirement that any scan or long-running task should provide a visible progress indicator.

## Added

- Background progress job for subtitle audit scans.
- Background progress job for subtitle job runner.
- Background progress job for Post Processing folder preview scans.
- More granular Post Processing progress callback support in the engine.
- Downloader handoff progress job when sending selected episode search results to the configured download app.
- New `/logs` page with SickChill-style filtering, sorting, paging, and JSON detail inspection.
- New `/api/logs` endpoint with level, event type, text search, sort, direction, limit, and offset support.

## Improved

- `/subtitles` now shows progress instead of blocking silently while scanning downloaded episodes.
- `/postprocess` now shows progress while walking and matching the completed-downloads folder.
- Show detail episode search results now show downloader handoff progress when a result is queued.
- Active Jobs is now a stronger single place to monitor background work after switching screens.

## Validation

- Python compile check passed.
- JavaScript syntax check passed.
- v17.18.0 targeted tests added.
