# API

Core endpoints include show/episode retrieval, episode search, result grabbing, queue triage, provider health, operations summaries, retention preview/apply, season-pack search/grab, subtitles, upgrades and diagnostics.

When API authentication is enabled, send:
`Authorization: Bearer <token>`

Health endpoints remain available for monitoring.

The in-app **System** page exposes the currently supported core endpoint catalog.

## v13 endpoints
- `GET /api/scheduler/runs` — scheduler execution history.
- `GET /api/season-packs/downloads` — season-pack acquisition/progress history.
- `POST /api/upgrades/propers/<episode_id>/search` — search Proper/Repack candidates; `{"grab":true}` explicitly grabs the best candidate unless Simulation Mode blocks it.


## v14 endpoints
- `GET /api/queue/unified` — active episode and season-pack acquisitions.
- `GET /api/acquisitions/<kind>/<id>/events` — lifecycle event history.
- `GET /api/upgrades/replacements` — safe replacement history.
- `POST /api/upgrades/replacements/<id>/rollback` — restore a staged previous episode file.
- `POST /api/media-servers/<id>/refresh-target` — target a post-import media refresh by show/path when supported.


## v15 endpoints
- `GET /api/naming/preview/<episode_id>` — calculate the configured final filename/path for an episode.
- `GET /api/library/fingerprint-conflicts?limit=500` — scan cached content fingerprints for duplicate media.
- `GET /api/scheduler/leases` — list active scheduler job leases.


## v16 endpoints
- `GET /api/security/status` — browser-auth setup state; remote unauthenticated callers receive redacted administrator details.
- `POST /api/security/password` — set/change administrator credentials.
- `POST /api/security/browser-auth` — enable or disable browser authentication.
- `GET /api/security/events` — recent browser security events.
- `GET /api/naming/config` — current naming configuration and presets.
- `POST /api/naming/config` — validate and save naming configuration.
- `POST /api/naming/preview-sample` — render a multi-episode naming preview.
