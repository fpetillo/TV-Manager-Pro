# Trakt Discovery and Show Queue

TV Manager v17.11.0 adds a Trakt.tv discovery workflow and a SickChill-style all-shows grid.

## Trakt discovery

Open `/trakt` to load trending, popular, anticipated, most watched, or most played shows from Trakt.tv. Operators can also search Trakt by title and add a returned show directly to TV Manager.

Public discovery requires a Trakt client id/API key. Add it to `.env`:

```env
TRAKT_CLIENT_ID=your_trakt_client_id
```

Optional authenticated sync can use:

```env
TRAKT_ACCESS_TOKEN=optional_oauth_access_token
```

The app also supports saving these values from the Trakt Discover screen. Secrets are stored in the local SQLite settings table.

## Show Queue

Open `/show-queue` for a modern all-shows table inspired by SickChill's show list. It supports paging, filtering, and sortable columns:

- Next episode
- Previous episode
- Show
- Network
- Quality
- Downloaded episodes / total episodes
- Library size
- Active state
- Status

The API is server-side paged so very large imported libraries remain usable.

```text
GET /api/show-queue?limit=100&offset=0&sort=show&direction=asc
```

## Notes

Trakt discovery uses current Trakt API v2 headers. Public discovery endpoints require `trakt-api-key`; OAuth is optional for these discovery views. User-specific Trakt collection, history, watched-state, and watchlist sync should be implemented later with device-code OAuth so deployments do not require copying tokens manually.
