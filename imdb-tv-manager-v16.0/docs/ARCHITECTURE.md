# TV Manager Architecture

TV Manager is a local-first, modular television automation platform.

## Major modules
- `app.py` — Flask HTTP/UI routing and migration entry points.
- `engine.py` — scheduler, searching, download handoff, post-processing, metadata.
- `advanced.py` — scene/anime mappings, provider definitions, groups, webhooks, media servers.
- `ops.py` — provider health, rules, snapshots, path mappings, conflict diagnostics.
- `intelligence.py` — tags, filters, retention models, queue triage, season-pack planning.
- `completion.py` — retention execution, watched state, system health, API summary.
- `production.py` — subtitles, season-pack searching, upgrades, backup validation, diagnostics.
- `release.py` — season-pack grabbing and opt-in API security.

## Design principles
1. Preserve imported SickChill state.
2. Add schema changes without destructive migrations.
3. Make automation explainable and recoverable.
4. Default to localhost and opt-in to remote/API security.
5. Preview destructive lifecycle operations before applying them.
6. Keep providers/downloaders/media servers replaceable through adapters.


## Acquisition lifecycle
`lifecycle.py` owns the v14 acquisition state machine, transition audit trail, quality replacement guard, managed upgrade staging, rollback, and unified queue projection.

The downloader engine records download progress but does not call a downloader-complete item "Completed". Downloader completion becomes `Downloaded`; post-processing advances the acquisition through `Importing` to `Completed`. This keeps transport completion distinct from successful library import.

`dbcore.py` is the only intended SQLite connection factory. Managed connections use WAL/busy timeout/foreign keys and close at `with`-block exit.

## Naming, integrity and scheduler guards
`naming.py` renders imported SickChill naming patterns and owns filename sanitization/sidecar destination calculation.

`integrity.py` owns cached media fingerprints used for content-level duplicate detection.

`scheduler_guard.py` owns cross-process scheduler leases. `engine.run_job()` must acquire a lease before creating a scheduler run and releases it in `finally`.


## Browser security

`security.py` owns administrator credentials, PBKDF2 verification, browser-auth state, login throttling, security events, CSRF token generation, and loopback detection.

`app.py` owns request enforcement because it must coordinate Flask sessions with bearer API-token authentication. Bearer-token requests bypass browser CSRF but are written to `api_access_log`.

`metadata_service.py` owns scheduler-safe stale-show metadata refresh. It fetches remote data before opening the SQLite write transaction.
