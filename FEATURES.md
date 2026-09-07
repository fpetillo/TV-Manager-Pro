## v17.13.3 Windows EXE Builder Fix

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

## v17.10.0 Responsive fit and product polish

- Sidebar-aware layout across migration and search pages.
- Mobile/tablet navigation toggle.
- Safer table overflow for large libraries and post-processing previews.
- Better wrapping for long filesystem paths and API diagnostics.
- Responsive Import Center and Post Processing controls.

# TV Manager v5.0 Feature Matrix

## Implemented
- SickChill database migration
- SickChill config.ini migration
- Full imported configuration browser/editor with secret masking
- Professional dashboard and navigation
- Show library search/filter
- Season-collapsed episode management
- Per-show monitoring/search controls
- Per-season bulk status controls
- Per-episode monitoring/status controls
- TMDb metadata refresh
- Existing library file reconciliation
- Upcoming and missing views
- Newznab provider searching
- Release scoring: resolution/source/codec/proper/repack/preferred/required/ignored words
- Reusable quality profiles and per-show profile assignment
- SABnzbd connection test and queue handoff
- qBittorrent connection test and handoff foundation
- Blackhole handoff
- Recent and backlog search jobs
- Scheduler and automation safety hold
- Download history/activity log
- Failed-release blacklist and retry workflow
- Post-processing preview and move/copy/hardlink execution
- Notification service inventory and email test
- Database backup before upgrade
- Health/status API

## Compatibility retained from SickChill config
The entire imported config remains available under Settings > All Imported Settings,
including provider, downloader, metadata, Kodi/Plex/Emby, subtitles, anime, notifications,
failed-download, GUI and advanced sections.

## Still being expanded for full parity
- Full Torznab/torrent-provider searching across every legacy provider implementation
- NZBGet, Transmission, Deluge, rTorrent and Synology downloader implementations
- Downloader completion polling for clients beyond SABnzbd; qBittorrent health/progress is visible but per-download hash correlation is still being expanded
- Subtitle provider searching/downloading
- XEM/scene numbering and DVD order translation
- AniDB/anime-specific release parsing
- Kodi/Plex/Emby live notification dispatch
- Metadata/NFO/artwork file generation (implemented for show/episode NFO + poster)
- Multi-episode release parsing
- Proper/repack upgrade scheduling
- Native Windows service packaging / installer


## v6.0 additions
- Generic custom Newznab/Torznab provider definitions + capability test
- NZBGet connection test and queue handoff
- Transmission connection test and torrent submission
- Deluge connection test and torrent submission
- Scene-season / scene-episode mappings and show aliases
- Anime absolute-number storage and editing
- Multi-episode release parsing (`S01E01E02`, `S01E01-E03`, `1x01-1x03`)
- User-defined show groups
- Event webhooks for external automation
- Plex, Jellyfin, Emby, and Kodi connection tests and library refresh actions
- Release Parser Lab for testing naming rules
- Advanced configuration page


## v6.1 additions
- Custom Newznab/Torznab providers now participate in real episode searches
- Provider-result de-duplication across sources
- Show-group filtering in the main library
- Local subtitle audit for downloaded episodes
- Post-processing webhooks for `downloaded`
- Optional automatic media-server refresh after post-processing
- Manual ZIP backup of the TV Manager database with manifest


## v7.0 — beyond parity
- Provider health metrics: successes, failures, latency and success rate
- Automatic provider circuit breaker with exponential cooldown after repeated failures
- Search-decision audit records and visible rule explanations
- Composable automation rules for scoring, rejecting and accepting releases
- Simulation mode: full search/scoring without automatic downloader submission
- Transactional configuration snapshots and restore
- Root-folder reachability and writeability diagnostics
- Remote-to-local path mappings for downloader/library topology
- Duplicate path / multiple-file conflict detection
- Operations console that centralizes reliability diagnostics
- Post-processing honors configured path mappings


## v8.0 — product intelligence & ergonomics
- Global command palette (`/`) for shows, episodes, pages and IDs
- Queue triage page with filtering, notes, fail/retry
- Dashboard insight cards that surface operational attention areas
- Show favorites
- Reusable tags and per-show tag assignment
- Saved-filter data model and API
- Retention-policy framework and protected episode locks
- Season-pack planning intelligence based on missing-episode density
- Release queue notes
- Deep links from command search directly to a show
- Refined product UI: sticky nav, command palette, insights, improved spacing and responsive surfaces


## v9.0 — completion & safety
- System health center and core API catalog
- Functional retention preview engine
- Safe retention apply: moves files to managed trash instead of permanent deletion
- Watched-state storage with profile/source attribution
- Episode protection integrates with retention safety
- Retention run audit schema
- API token foundation for future remote clients
- Upgrade-history schema
- Deployment diagnostics and database quick-check
- Versioned platform system page


## v10.0 — production completion
- Actual season-pack provider search across built-in Newznab and custom Newznab/Torznab
- OpenSubtitles-compatible provider configuration, subtitle search and download engine
- Downloaded-episode upgrade planner driven by quality-profile cutoffs
- Backup ZIP validation plus SQLite integrity validation
- Redacted diagnostic-bundle generation
- System diagnostics bundle download
- Subtitle provider UI
- Windows Task Scheduler startup installer/uninstaller
- Sync-history, upgrade-history and subtitle-download audit schemas
- Production integration layer kept additive to existing migrated database


## Library Health hardening

- Works against empty, partially migrated, and legacy-imported databases.
- Separates missing-on-disk files from episodes without file locations.
- Shows schema warnings and recoverable UI errors instead of a blank page.


## Production replacement features

- Server replacement runbook for SickChill cutover.
- Linux systemd installation helper.
- Read-only server preflight report before migration.
- Documented Caddy/Nginx reverse proxy patterns.
- Backup and rollback process for safe replacement.


## v17.3 Product Experience

- Cohesive professional dark UI designed for local/server operations.
- Active page navigation across major screens.
- Polished dashboard, migration, health and library surfaces.
- Consistent visual treatment for safe workflows and support/version verification.


### v17.3.4 Import Reliability

- SickChill imports commit cleanly and close database handles before verification.
- Post-import active database counts are returned with each import response.
- Regression-tested against immediate follow-up reads/writes to avoid locked-database surprises.

## v17.4 Operator Workflow

- Workflow cockpit for install → import → validate → configure → cutover.
- Action-oriented readiness snapshot and recommendations.
- Guided Import Center ribbon.
- Operator workflow documentation for full SickChill replacement.


## v17.7.0 Navigation and Distribution

- Categorized left navigation: Command, Library, Acquisition, Migration, Platform.
- Responsive sidebar layout for professional operator workflows.
- Cross-platform installation documentation.
- Windows EXE installer build assets.


## v17.9.1 Large Library Performance

- Server-side pagination for the Shows API.
- Operator-friendly Library loading and error states.
- `Load next` paging workflow for very large imports.
- Database indexes for faster library search and season browsing.



## v17.9.1 Post Processing

- Configured completed-TV folder.
- One-time override folder.
- Preview-first scan.
- Selectable post-processing actions.
- Safe move/copy/hardlink workflow.
- Responsive sidebar-era layout fixes.

## v17.9.1 Metadata Reliability

- Shared TMDb client for search, show refresh, and metadata batch refresh.
- Supports bearer-token and legacy API-key authentication.
- Safe metadata status endpoint that does not expose secrets.
- Clear operator-facing errors for missing or unauthorized TMDb credentials.

## v17.12.0 - Full Metadata Refresh + Show Queue Date Fix

- Added full-library metadata refresh from Library Health with preview, background progress, counts, and failed-item details.
- Added full metadata refresh job APIs.
- Fixed Show Queue Next Ep / Prev Ep values so dates are normalized and displayed as readable calendar dates.
- Added full-library metadata refresh documentation.


## v17.13.2 Windows EXE Build Safety

- Fixed recursive Windows EXE build staging.
- Build output now publishes to `release/windows/TVManager`.
- PyInstaller is invoked through the project virtual environment.

## v17.14.0 — Database Protection + Progress Polish

- Added Database Safety Center at `/database-safety`.
- Added verified SQLite backups using the SQLite backup API, with quick-check validation and SHA-256 records.
- Added redacted configuration snapshots so `.env` and runtime settings are protected without exposing secrets.
- Added backup manifest tracking under `backups/db-backup-manifest.json`.
- Added shared progress job APIs and converted Library Health scanning to a progress-bar workflow.
- Added `protect_db.py` for command-line backup and backup inventory scans.
## v17.15 Professional automation polish

- Active Jobs monitor at `/jobs`.
- Background episode/search/post-processing/metadata jobs continue while switching screens.
- Configurable scheduler entries for missing metadata, episode/show artwork, Library Health and database protection.
- Episode art fields from TMDb for better media-center metadata.



## SickChill Parity Manage Center

- Backlog Overview grouped by show.
- Recent/backlog searches as background jobs.
- Episode Status Management with preview/apply safety.
- Failed-release blacklist management.
- Missed subtitle management.
- Scene exceptions for alternate release names.
- Combined mass refresh for metadata, artwork and subtitles.


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
