# TV Manager v17.16.0 — SickChill Parity Manage Center

This release adds a new SickChill-style Manage center and fills several expected day-to-day management gaps.

## Added

- New `/manage` page.
- Backlog Overview grouped by show.
- Background Recent Search and Backlog Search controls.
- Episode Status Management preview/apply workflow.
- Failed Downloads blacklist review/add/remove.
- Missed Subtitle Management list.
- Scene Exceptions table for alternate release names.
- Mass Refresh background job for missing metadata, artwork, and optional subtitle scanning.
- Navigation and command-palette entries for Manage workflows.

## New APIs

```text
GET    /api/manage/summary
GET    /api/manage/backlog-overview
POST   /api/manage/episode-status/preview
POST   /api/manage/episode-status/apply
GET    /api/manage/failed-downloads
POST   /api/manage/failed-downloads
DELETE /api/manage/failed-downloads/<failed_id>
GET    /api/manage/missed-subtitles
GET    /api/manage/scene-exceptions
POST   /api/manage/scene-exceptions
DELETE /api/manage/scene-exceptions/<exception_id>
POST   /api/manage/mass-refresh/start
```

## Validation

- Python compile check passed.
- JavaScript syntax check passed.
- Full test suite passed.
