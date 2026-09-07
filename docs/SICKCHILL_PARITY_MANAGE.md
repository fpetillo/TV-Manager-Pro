# SickChill Parity Manage Center

TV Manager v17.16.0 adds a modern `/manage` screen for the SickChill-style management workflows that operators expect during daily use.

## Included surfaces

- **Backlog Overview** — groups aired Wanted/Failed episodes by show so the operator can see where the backlog is concentrated.
- **Manage Searches** — launches Recent Search and Backlog Search as background jobs so the process continues while the operator switches pages.
- **Episode Status Management** — previews large status changes before applying them, then applies the change as a background job.
- **Failed Downloads** — lists failed-release blacklist entries and allows manual blacklist/remove actions.
- **Missed Subtitle Management** — shows downloaded episodes currently marked as missing subtitles and links back to the Subtitles page.
- **Scene Exceptions** — records alternate show names used by release groups and provider/indexer listings.
- **Mass Refresh** — queues a combined maintenance job for missing metadata, show/episode artwork, and optional subtitle scanning.

## Main page

```text
/manage
```

## APIs

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

## Safety behavior

Episode Status Management requires a preview before the operator applies a change. The apply step runs as an Active Job and writes a `mass_update_history` row. Failed-release entries are stored in the existing `failed_releases` blacklist table used by episode grabbing logic.

## Next parity work

Future releases should deepen provider-specific scene exception matching, add XEM-style absolute/scene numbering support, expand subtitle provider automation, and add richer download-client retry/quarantine controls.
