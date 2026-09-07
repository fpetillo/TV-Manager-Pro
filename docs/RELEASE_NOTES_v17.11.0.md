# TV Manager v17.11.0 - Trakt Discovery + Show Queue

This release adds two major SickChill replacement features:

1. Trakt.tv show discovery for adding popular, trending, anticipated, watched, played, and searched shows.
2. A modern SickChill-style Show Queue grid for viewing all shows in one sortable, filterable table.

## Added

- `/trakt` Trakt discovery page.
- `/api/trakt/status` safe credential status endpoint.
- `/api/trakt/settings` local settings save endpoint.
- `/api/trakt/shows` discovery/search endpoint.
- `/api/trakt/add-show` endpoint for adding a Trakt show to the library.
- `/show-queue` all-shows grid.
- `/api/show-queue` server-side paged grid API.
- Support for `TRAKT_CLIENT_ID`, `TRAKT_API_KEY`, `TRAKT_CLIENT_KEY`, and optional `TRAKT_ACCESS_TOKEN`.
- New `trakt_client.py` shared client module.
- Database columns/indexes for Trakt IDs and high-volume show queue browsing.

## Improved

- Left navigation now includes Trakt Discover and Show Queue.
- Large-library browsing gets a familiar full-table option in addition to the existing detail-first Manager page.
- Show Queue has sortable columns and filters without rendering the full library at once.

## Operator setup

Add this to `.env` and restart TV Manager:

```env
TRAKT_CLIENT_ID=your_trakt_client_id
```

Then open:

```text
http://127.0.0.1:5050/trakt
http://127.0.0.1:5050/show-queue
```
