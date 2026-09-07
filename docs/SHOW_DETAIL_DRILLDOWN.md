# Show Detail Drill-Down

TV Manager v17.13.0 turns the Show Queue into a true operator command center.

## Workflow

1. Open `/show-queue`.
2. Filter or sort the all-shows grid.
3. Click a show title.
4. TV Manager opens `/show/<show_id>`.
5. Filter episodes by season, status, or search text.
6. Click **Search** beside the episode you want to find/download.
7. Send an approved release to the configured downloader.

## API

```text
GET /show/<show_id>
GET /api/shows/<show_id>
GET /api/shows/<show_id>/episodes?all=1&limit=100&offset=0&q=&season=&status=&sort=season_episode&direction=asc
POST /api/episodes/<episode_id>/search
POST /api/search-results/<result_id>/grab
PATCH /api/episodes/<episode_id>
```

The episode endpoint keeps the older season-summary behavior when no drill-down filters are supplied, so the classic Manager screen remains compatible.
