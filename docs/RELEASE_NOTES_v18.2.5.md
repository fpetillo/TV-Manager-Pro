# TV Manager v18.2.5 — Show Detail No-Wait Hotfix

This hotfix changes Show Detail loading from cosmetic progress to a true no-wait fallback.

## Fixes

- Added a never-hang show snapshot endpoint for first paint.
- Added a never-hang episode-lite endpoint for the first episode page.
- Added a hard client-side watchdog so the page stops waiting after a short interval and shows Retry / Jobs / Logs.
- Reduced first episode page default retry path to 25 episodes when a database read is blocked.
- Kept full counts and heavier aggregation as follow-up work after the page becomes usable.

## New endpoints

- `GET /api/shows/<id>/snapshot`
- `GET /api/shows/<id>/episodes-lite`

## Operator impact

If a background scan or SQLite writer blocks the normal episode table, Show Detail should no longer sit forever on Loading. It will show a usable failure state with retry actions instead.
