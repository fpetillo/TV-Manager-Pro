

## v18.2.1 - Show Load Progress Polish
- Added visible loading/progress indicators while opening a show from Show Queue.
- Added Show Detail header progress while show metadata, season counts, and episode rules load.
- Added episode-table progress row while episodes are loading or filters refresh.
- Added an indeterminate progress style for operations that are actively waiting on API/database responses.


## Version 18.2.0 — Bulk Episode Management & Ignore Rules

- Adds SickChill-style bulk episode management.
- Adds episode-level ignored/not-considered rules.
- Adds Show Detail controls for selected episodes, filtered missing episodes, and Season 00 / Specials.
- Adds Manage page filters for Specials-only and Ignored-only operations.
- Excludes ignored episodes from wanted/missing/search/count logic while keeping them visible for audit and re-include.
- Adds docs/EPISODE_BULK_MANAGEMENT.md and docs/RELEASE_NOTES_v18.2.0.md.

## Version 18.1.0 — SickChill Queue Counts & Season 00 Ignore

- Show Queue and Download Queue now sort SickChill-style by missing episode count first, then downloaded/total counts.
- Queues now show missing episode numbers and downloaded totals for each show.
- Added a TV Manager setting to ignore Season 00 / Specials in show counts, missing totals, downloaded totals, and progress meters while preserving S00 episodes in the database.
- Added API support for `ignore_season_zero_counts`, `missing_episode_numbers`, and queue count metadata.

## v17.13.3 - Windows EXE Robocopy Quoting Patch

## v17.21.0 — SQLite Lock Guard + Media Server Maintenance

- Added SQLite writer serialization and longer busy timeout to prevent background scheduler/database lock crashes.
- Added retry-safe scheduler finish and logging updates.
- Added full edit/delete maintenance for media servers and other Advanced configuration records.
- Added background job monitoring for media server test, refresh and watched-sync operations.
- Improved downloader handoff failure reporting.


- Fixed the Windows EXE build script so ROBOCOPY handles paths with spaces correctly.
- Build staging remains outside the app folder and excludes runtime data, databases, secrets, logs, imports, and old output.
- Final EXE output remains under `release/windows/TVManager`.


- v17.13.2 adds Show Queue drill-down: click a show to open `/show/<id>`, filter/search episodes, and search/download from the episode row.
## v17.13.2 - Trakt Discovery + Show Queue

- Added Trakt.tv discovery for trending, popular, anticipated, watched, played, and search-driven show additions.
- Added a modern SickChill-style Show Queue at `/show-queue` with sortable columns and server-side paging.
- Added `/api/trakt/*` endpoints, `/api/show-queue`, and Trakt credential setup documentation.
- Added Trakt identity columns/indexes and performance indexes for all-shows browsing.

# TV Manager v17.10.0

TV Manager is a professional SickChill replacement focused on guided migration, scalable library management, metadata refresh, post-processing, and operator-friendly deployment.

This build adds the responsive fit polish needed after the left navigation redesign. Import Center, Post Processing, large-library tables, long file paths, and smaller browser windows are handled more cleanly.


# TV Manager

**Current version: 17.9.1**

TV Manager is a local-first television automation platform designed as a modern successor to SickChill-class managers. It combines migration, provider search, download-client orchestration, post-processing, quality/upgrade policy, subtitles, diagnostics, explainable automation, media-server integration and recovery-focused operations.


## What changed in v17

v17 starts the dedicated migration-hardening phase. SickChill database imports now have a no-write analysis endpoint, a dry-run preview endpoint, an idempotent importer, a legacy identity map, and a per-item audit trail so repeat imports are safe and explainable.

Library maintenance also gains a duplicate-candidate API built on the v15 fingerprint cache, and metadata refresh can be triggered as a bounded API job for safe operator-controlled runs.

See [v17 release notes](docs/RELEASE_NOTES_v17.md).

## What changed in v14

v14 completes a major reliability loop: downloads have a persistent acquisition lifecycle, season packs share the same Queue, upgrades are staged and rollback-capable, recognized downgrades are blocked, subtitle retries back off automatically, and Plex can receive a targeted post-import path scan instead of refreshing every library.

See [v14 release notes](docs/RELEASE_NOTES_v14.md) and [acquisition lifecycle](docs/ACQUISITION_LIFECYCLE.md).



## What changed in v16

v16 adds optional browser authentication for local/LAN installations, CSRF protection for authenticated browser writes, failed-login throttling, security event history, and a production-server guard that refuses LAN binding until an administrator account exists and browser authentication is enabled.

Naming is now configurable from the Settings UI with presets and a live multi-episode preview. Scheduled post-processing can finally run live when the imported SickChill `process_automatically` setting is enabled and Simulation Mode is off.

The metadata scheduler is also real in v16: it refreshes a small batch of stale shows each run, tracks per-show refresh state, and performs network requests before opening the SQLite write transaction.

## What changed in v15

v15 turns imported SickChill naming settings into real post-processing behavior. Preview Scan now calculates the exact final library path before a file moves, including multi-episode filenames. Post-processing can rename associated subtitle/NFO/artwork files with the episode, caches content fingerprints for duplicate detection, and keeps the v14 safe-upgrade rollback path.

Scheduler jobs now use database-backed leases so a second TV Manager process cannot run the same automation job concurrently. Stale `Running` jobs are recovered as `Abandoned` after restart.

For an always-on Windows installation, v15 adds an optional Waitress production runner while preserving the existing `run.ps1` workflow.

## Start
On Windows:
```powershell
.\setup.ps1
.\run.ps1
```

Open `http://127.0.0.1:5050/dashboard`.

## Validate
```powershell
.\validate-release.ps1
```

## Documentation
- [Feature catalog](docs/FEATURES.md)
- [Architecture](docs/ARCHITECTURE.md)
- [SickChill migration](docs/MIGRATION.md)
- [Operations](docs/OPERATIONS.md)
- [Security](docs/SECURITY.md)
- [API](docs/API.md)
- [Roadmap](docs/ROADMAP.md)
- [Watched-state synchronization](docs/WATCHED_STATE.md)
- [Database reliability](docs/DATABASE_RELIABILITY.md)
- [Fresh Windows PC Installation](docs/WINDOWS_FRESH_INSTALL.md)
- [Windows Deployment](docs/WINDOWS_DEPLOYMENT.md)
- [Browser & LAN Security](docs/BROWSER_SECURITY.md)
- [Acquisition lifecycle](docs/ACQUISITION_LIFECYCLE.md)
- [Changelog](CHANGELOG.md)

## Repository hygiene
Never commit `.env`, `tvmanager.db`, backups, diagnostics, logs or imported credentials.


---

## Historical release notes

# TV Manager v10.0

v10 is the production-completion pass.

Major additions:
- season-pack provider searching
- OpenSubtitles-compatible subtitle acquisition
- quality-profile upgrade planner
- validated backup plumbing
- redacted diagnostic bundles
- Windows startup installation

Preserve the existing `tvmanager.db` and `.env`. All schema upgrades are additive.
Run `setup.ps1` if needed, then `run.ps1`. For automatic Windows startup, run
`install-startup.ps1` in PowerShell.


# TV Manager v9.0

This release is the completion/safety pass for the modern TV automation platform.

The emphasis is no longer simply adding screens: v9 turns previously scaffolded lifecycle features into safe operational behavior. Retention can be previewed and applied, protected episodes are excluded, watched-state is stored, files are moved to managed trash rather than permanently deleted, and a System center provides deployment/database diagnostics plus an API catalog.

Keep your existing `tvmanager.db` and `.env`; schema upgrades are additive.


# TV Manager v8.0

v8 focuses on product intelligence and UI/UX rather than raw parity alone.

Highlights:
- global command palette
- queue triage
- dashboard insights
- favorites, tags and saved-filter foundation
- retention-policy and episode-lock foundation
- season-pack planning intelligence
- major visual polish across the application

The goal is a manager that is faster to operate, easier to understand, and safer to automate than legacy TV managers.
Keep your existing `tvmanager.db` and `.env`.


# TV Manager v7.0

v7 moves the project from feature parity toward an operations-first automation platform.

The new **Operations** area adds:
- provider reliability scoring and automatic circuit breakers
- path/root diagnostics
- duplicate/conflict detection
- composable automation rules
- configuration snapshots with transactional restore
- simulation mode
- search-decision explanations

This is designed to make automation auditable and recoverable, not opaque.
Keep the existing `tvmanager.db` and `.env`.


# TV Manager v6.1

Connects the v6 advanced features to the real automation path and adds subtitle auditing, show-group filters, automatic media-server refresh after processing, webhook events, and downloadable database backups.

# TV Manager v6.0

v6 expands the parity layer and begins the "beyond SickChill" feature set.

New in this build:
- custom Newznab/Torznab provider definitions
- NZBGet, Transmission, and Deluge integration
- scene/anime mappings and aliases
- multi-episode release parsing
- show groups
- webhooks
- Plex/Jellyfin/Emby/Kodi integrations
- Release Parser Lab and Advanced configuration page

Keep your existing `tvmanager.db` and `.env`.


# TV Manager v5.1

Adds show/episode NFO generation, poster artwork writing, SABnzbd history polling, qBittorrent status polling, and manual downloader polling from Settings.

# TV Manager v5.0

Professional SickChill-replacement release.

Keep the existing `tvmanager.db` and `.env`. v5.0 migrates the database in place and
preserves the prior SickChill migration.

Start with `run.ps1`, then open:

- `/dashboard` — operational overview
- `/manager` — show/season/episode management
- `/upcoming` — upcoming episodes
- `/missing` — missing/wanted backlog
- `/activity` — search/download history
- `/postprocess` — completed-download processing
- `/quality` — quality profiles
- `/settings` — automation, downloaders, providers, notifications, and all imported SickChill settings
- `/import` — migration tools

Automation remains paused until explicitly armed.


# TV Manager v4.1

Reliability and library-management pass on top of v4.0.

## Added
- Automatic one-time backup of `tvmanager.db` before the v4.1 upgrade
- Per-show pause/search/monitor/season-folder controls
- Per-show preferred, required and ignored release words
- Existing-library scan for each show
- Per-episode status editing and monitor toggle
- Season-wide bulk status changes
- Health endpoint and richer TV Manager settings state
- Existing files matched during library scan are marked Downloaded without deleting legacy metadata

Backups are stored under `backups/`.


# TV Manager v4.0 — SickChill replacement foundation

v4.0 turns the migration utility into an operational TV automation manager.

## Added
- Modern navigation: Shows, Upcoming, Missing, Activity, Post Processing, Settings, Import
- Season-collapsed library from v3.5 retained
- Normalized SickChill episode statuses while preserving original legacy JSON
- Per-episode manual search
- Newznab provider migration and search support
- Provider priority/randomization support
- Ignore / prefer / require word scoring
- Release quality inference and scoring
- Search result history
- SABnzbd connection testing and NZB submission
- qBittorrent connection testing and torrent submission foundation
- Blackhole handoff support
- Snatched status and download history
- Failed-release blacklist schema
- Recent-search and backlog-search engines
- Scheduler with imported SickChill frequencies
- Migration safety hold: automation remains paused until explicitly armed
- Upcoming and Missing/Wanted pages
- Activity and download history
- Post-processing preview and execution foundation
- Per-show monitoring/search/format columns for future scene/anime/sports behavior

## Important startup behavior
Keep your existing `tvmanager.db` and `.env`. v4.0 migrates the existing database in place.

Automation is deliberately PAUSED after migration. Go to **Settings**, test your configured download clients, then arm automation when ready.

## Notes
The provider/download architecture is intentionally modular. Newznab + SABnzbd and qBittorrent are the first fully wired legacy paths because they are present in the imported SickChill configuration. More provider protocols, NZBGet, Transmission, Deluge, notifications, subtitles, scene/XEM mapping, anime-specific numbering, richer quality profiles, and downloader completion polling can be added on the same engine without another database migration.


# IMDb TV Manager v3.5

Adds TMDb metadata refresh for imported SickChill shows. It resolves shows from existing IMDb/TVDb IDs, updates posters/overview/network/genres/IDs, loads seasons and episodes, and preserves existing SickChill locations/status values.

# IMDb TV Manager v3.4

Adds a redesigned manager with instant show search, status filters, dashboard totals, single-show detail view, and collapsed season-by-season episode browsing.

# IMDb TV Manager v3.3

Adds SickChill config.ini import and settings preservation.

Keep your existing tvmanager.db and .env, start v3.3, open /import, and import config.ini.

# IMDb TV Manager v3.2

**Fix:** automatically converts older `shows.tmdb_id NOT NULL` schemas to a nullable TMDb ID so SickChill shows without a TMDb mapping can be imported. Existing show IDs and data are preserved.

# IMDb TV Manager v3.1

**Fix:** automatically upgrades databases from v2/v3 by adding missing columns such as `tvdb_id` without deleting existing shows.

# IMDb TV Manager v3

This build adds SickChill database migration.

## Test it

1. Unzip into a new folder.
2. Run:
   `Set-ExecutionPolicy -Scope Process Bypass`
   `.\setup.ps1`
3. Copy your existing TMDb Read Access Token into `.env`.
4. Start with `.\run.ps1`
5. Open `http://127.0.0.1:5050/import`
6. Select your SickChill `sickbeard.db`.
7. After import, open TV Manager.

The importer makes an untouched backup copy, auto-detects common `tv_shows` / `tv_episodes` tables, imports shows and episodes, prevents duplicates, and stores each original legacy row in JSON for later exact reconciliation.

Episode status values are preserved exactly instead of being guessed because older SickChill builds may encode status and quality together.


### Library Health Dashboard

TV Manager v17.1 adds `/library-health` for post-import checks, missing files, metadata gaps, duplicate candidates, and safe duplicate cleanup previews. v17.1.2 hardens this page for empty, partially migrated, and legacy-imported databases and separates files missing on disk from episodes that simply have no file location yet. Cleanup apply operations move files to `managed_trash` and record audit rows; files are never deleted directly.


## Version visibility

The running version is visible in the global footer, the `/about` page, the System page, and the `/api/version` endpoint.


## Route diagnostics

TV Manager v17.1.8 adds `/routes` and `/api/routes` to verify the running Flask route map. If About or Library Health return the plain Flask Not Found page, stop the running server, confirm the installation folder contains `VERSION` = `17.1.8`, and restart from that same folder.

### v17.1.8 startup repair note

If startup fails with `sqlite3.OperationalError: no such column: imdb_id`, install v17.1.8 or newer and restart from the upgraded folder. This build repairs older `shows` tables by adding `imdb_id` before the IMDb index is created.


## SickChill server replacement

TV Manager now includes a full production runbook for installing on the same server currently running SickChill and replacing it safely. Start with:

- `docs/SICKCHILL_REPLACEMENT_SERVER_INSTALL.md`
- `docs/PRODUCTION_LINUX_DEPLOYMENT.md`
- `server_preflight.py`
- `scripts/install-linux-service.sh`

The recommended approach is side-by-side installation, importing from a copy of SickChill's database, validating Library Health, then disabling SickChill only after TV Manager has been verified.


## Product experience

Version 17.3.1 introduces a cohesive professional interface refresh so TV Manager feels like a complete replacement product: unified navigation, polished cards and panels, active route highlighting, page-level product heroes, and consistent support/version visibility. See `docs/UI_DESIGN_SYSTEM.md`.


## Version 17.7.0 - Setup Assistant and Cutover Polish

Version 17.7.0 adds `/setup-assistant`, a guided operator checklist for completing SickChill replacement safely: install side-by-side, import, validate Library Health, configure automation, and cut over only when blockers are resolved.

## Version 17.5.0 - Launchpad Experience

Version 17.5.0 adds a premium Launchpad at `/launchpad` with readiness scoring, operator next actions, health counts, migration/cutover guidance, and a more intuitive product workflow.

## Version 17.3.5 - Import job startup fix

Version 17.3.5 fixes the asynchronous SickChill import job startup error where the import helper received `job_id` twice. The Import Center progress job endpoint now starts cleanly and reports progress instead of failing before the job is queued.

## v17.4 Workflow Cockpit

Open `/workflow` after startup for a guided replacement cockpit covering import, validation, operations, and SickChill cutover readiness.


## Distribution Readiness

TV Manager now includes a categorized left-side navigation model and expanded install documentation for Windows, Linux, macOS, server replacement, and Windows EXE installer packaging. See `docs/INSTALL_ALL_PLATFORMS.md` and `docs/WINDOWS_EXE_INSTALLER.md`.


## Version 17.9.1 - Large Library Performance

Version 17.9.1 fixes the large-library freeze seen after importing very large SickChill databases. The Library / Shows screen no longer requests every show in a single response. It now uses server-side pagination, loads the first 100 shows immediately, and lets the operator load additional pages on demand. This makes 39K+ imported records manageable and prevents the browser from appearing stuck at `Showing...`.



## v17.9.1 Post Processing workflow

TV Manager now includes a SickChill-style Post Processing screen with a configured completed-TV folder, one-time override folder, preview-first scan, selectable rows, and safe Process Selected / Process All Approved actions. See `docs/POST_PROCESSING_WORKFLOW.md`.

### TMDb metadata credentials

Metadata refresh supports either `TMDB_BEARER_TOKEN` or legacy `TMDB_API_KEY` in `.env`. Check `/api/metadata/status` after startup to confirm that TV Manager can see the credential without exposing the secret.

## v17.12.0 - Full Metadata Refresh + Show Queue Date Fix

- Added full-library metadata refresh from Library Health with preview, background progress, counts, and failed-item details.
- Added full metadata refresh job APIs.
- Fixed Show Queue Next Ep / Prev Ep values so dates are normalized and displayed as readable calendar dates.
- Added full-library metadata refresh documentation.

## v17.14.0 — Database Protection + Progress Polish

- Added Database Safety Center at `/database-safety`.
- Added verified SQLite backups using the SQLite backup API, with quick-check validation and SHA-256 records.
- Added redacted configuration snapshots so `.env` and runtime settings are protected without exposing secrets.
- Added backup manifest tracking under `backups/db-backup-manifest.json`.
- Added shared progress job APIs and converted Library Health scanning to a progress-bar workflow.
- Added `protect_db.py` for command-line backup and backup inventory scans.
### v17.15.0 Professional background jobs and scheduler

TV Manager now includes an Active Jobs screen at `/jobs`, expanded Scheduler maintenance for missing metadata, show/episode artwork, Library Health and database protection, and progress-bar workflows for long operations such as episode search, show metadata refresh and post-processing.



## v17.16.0 SickChill Parity Manage Center

Adds `/manage` with Backlog Overview, Manage Searches, Episode Status Management, Failed Downloads, Missed Subtitle Management, Scene Exceptions and a Mass Refresh background job.


## v17.19.0 - Progress Everywhere + Professional Logs

- Subtitle audit scans now run as background jobs with progress bars.
- Post Processing folder preview scans now run as background jobs with progress bars.
- Sending selected search results to the configured downloader now has a monitored progress job.
- Added `/logs`, a SickChill-style sortable/filterable event log viewer.
- Added `/api/logs` with level, event type, search, sort, direction, limit and offset filters.


## v17.21.0 - Episode Search Return Navigation

- Returns to the show episode list after sending a search result to the downloader.
- Preserves episode list context and scroll position.
- Adds Back to Episodes controls inside the episode search modal.
- Adds Show Detail links to Download Center and Active Jobs.

## v17.22.0 - Operations Progress Everywhere Audit

- Converted Operations scan buttons to visible progress/background-job workflows.
- Added progress-aware Root & Path Health check, Library Conflict scan, Content Duplicate fingerprint scan, and Config Snapshot creation.
- Added progress-aware Scan Existing Files / Scan Existing Folder workflow from the show manager.
- Added tests enforcing that Operations scan actions expose progress indicators and background job APIs.

## v17.23.0 - Show Queue Polish & Sort Accuracy

- Fixed Show Queue Downloads sorting to use numeric downloaded episode counts.
- Added stable sort indicators and better default sort direction for numeric columns.
- Normalized legacy SickChill ordinal dates in the Show Queue so numeric airdate artifacts do not appear.
- Improved Downloads progress-bar state and numeric column alignment.

## v18.0.0 - Professional Polish Release

- Promotes TV Manager to Version 18.
- Adds Launchpad Version 18 readiness checklist.
- Adds `/api/system/release-readiness` for runtime polish verification.
- Adds safe Windows `release-and-push.ps1` GitHub source commit automation.
- Keeps Show Queue Downloads sorting based on real numeric downloaded counts.
- Updates documentation for Version 18 readiness and GitHub release automation.
