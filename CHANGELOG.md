## 18.5.14 — Aired episode queue progress

Show Queue now counts only episodes with a valid airdate on or before today (server local date). Future and unknown dates no longer inflate downloaded/total, missing counts or missing episode numbers. Season summaries show missing / aired totals; fully unaired seasons are omitted. Ignored and globally excluded Specials remain excluded. Recorded file paths remain the downloaded criterion; no disk scan is performed. Future shows remain listed with No aired episodes, and Next Ep retains upcoming information.

Default sorting prioritizes missing share of aired episodes, then missing count. The Sort by Missing / Aired button restores that priority; the Downloads column retains count-based sorting. Sorting happens before pagination. This ratio priority is a TV Manager design choice, not a claim that SickChill has the identical comparator.

Research: SickChill describes Downloads as downloaded versus aired episodes in https://github.com/SickChill/sickchill/wiki/Remaining-settings-explained and ignored episode exclusion in https://github.com/SickChill/sickchill/wiki/Episode-Status .

Validation: 307 tests passed and JavaScript/whitespace checks passed. API regression covers partial and future-only shows, unknown dates, ordinal imported dates, ignored/S00 exclusions, per-season counts and sorting before pagination. Isolated browser shows S01 1/1 missing with future S02 excluded. No production data changed. Restart and refresh Show Queue. Full SickChill parity remains incomplete.

## 18.5.13 — Editable configuration center

Settings now exposes All Configurable Settings, combining stored/imported configuration with a catalog of 64 literal application defaults extracted from current configuration readers. Sections and fields can be filtered; only changed fields are saved, and failed saves report the error and count already saved. Protected inputs use password fields and unchanged masked values are not resubmitted. Library roots direct users to Library Locations to retain shows-in-use validation.

Settings navigation now links to Library Locations, Quality Profiles, Metadata Sources, Native Notifications, Providers/Media Servers/Webhooks, Post-Processing, New Show Defaults and Database Protection. Client/provider/notification summary tabs have edit shortcuts. Search-default saves check HTTP success. Unsupported legacy SickChill settings remain editable but do not imply native behavior or full parity.

Validation: 306 tests passed; JavaScript syntax and whitespace checks passed. New regression verifies unsaved default discovery and stored override persistence without duplicates. Isolated browser edited recent_days from 14 to 21, saved and reopened to verify persistence. No production settings changed.

Restart TV Manager and refresh Settings. Startup-only options require a restart after editing. The catalog must be updated when new literal configuration readers are added; structured settings continue to use their linked dedicated editors.

## 18.5.12 — Visible library settings and global Specials

Added Library settings controls above Shows and Show Queue: Settings, Ignore S00 / Specials for All Shows, and a link to Manage / Include Specials Again. Explains where to edit individual shows. Reuses the existing global Specials workflow, confirms the total and whole-library scope regardless of current filters, reports job progress/errors and offers Refresh Shows on completion. Files are retained; existing Specials become ignored/unmonitored and the persistent global search/count exclusion also covers future Specials.

Validation: 305 tests passed and JavaScript syntax/whitespace checks passed. Isolated browser verified count confirmation, successful update of one synthetic Special, and controls on Show Queue. No production episode settings changed.

Refresh the browser for controls; restart for version label. Full SickChill parity remains incomplete.

## 18.5.11 — Find and download missing episodes

Open a show from Show Manager and choose **Find & Download Missing Episodes**. Confirm the eligible count to search all seasons and automatically send the best acceptable release for each episode to the configured downloader. Progress and errors appear in Active Jobs; the page can be closed during the search.

No scheduler per-run cap applies. Aired, monitored episodes without recorded files are included; ignored, unmonitored, downloaded, queued, unknown-airdate and future episodes are excluded. Show pause/search settings and the global Specials exclusion are respected. Repeated clicks reuse the active show job, and eligibility is checked again before each episode. Simulation mode searches without sending downloads. Provider failures do not stop remaining episodes. Release quality rules and the failed-release blacklist use the existing search pipeline.

Validation: 305 tests passed, including uncapped selection, exclusions, duplicate starts, simulation, error continuation, successful handoff and eligibility recheck. JavaScript syntax passed. Isolated browser verified button, count confirmation and completion using a mocked provider; no real downloads sent.

Restart TV Manager and refresh the show page. Download handoff is not download completion; unmatched episodes may remain missing. Full SickChill parity remains incomplete.

## 18.5.10 — TV Manager Pro branding

- Added the supplied original logo to shared navigation, Launchpad, and Dashboard.
- Kept page actions on their own row and scaled branding for smaller screens.

## 18.5.9 - 2026-09-08

Edit show names in Show Settings, with validated custom titles retained across metadata refresh. Folders/files unchanged. 301 tests pass; isolated browser save verified. Restart required.

## 18.5.8 - 2026-09-07

Collapsed season headings show downloaded/total episode counts using recorded file paths. Browser verified; 300 tests pass.

## 18.5.7 - 2026-09-07

Episode-count badges remain visible on collapsed season headings, including Specials. Uses grouped totals without loading episode rows. Browser verified; 300 tests pass.

## 18.5.6 - 2026-09-07

Fix Plex refresh for UNC/mapped-drive mismatches and TV libraries with multiple roots. Scan deduplication and failure logging. 300 tests pass; both configured Plex servers accepted live scan requests. Restart required.

## 18.5.5 - 2026-09-07

Job status filter buttons with counts, active grouping, exact status choices and selection preserved across refresh. 296 tests pass; live Failed filter verified.

## 18.5.4 - 2026-09-07

Collapsible season sections with Specials last, lazy full-season loading, filters and selection scoped to expanded seasons. No global episode paging. Browser verified expand/collapse and selection; 295 tests pass.

## 18.5.3 - 2026-09-07

Fix Show Detail initial load: separate page initializer from downloader handler so show/episode requests start automatically. Browser verified opening from queue without Refresh; 294 tests pass, including old-code failure regression.

## 18.5.2 - 2026-09-07

Regression coverage for manual episode search and retrieve using real SQLite rows. Reported error traced to live 18.3.3; dictionary conversion already exists in published code. Restart required after active processing. 293 tests pass.

## 18.5.1 - 2026-09-07

Prevent aired XEM mappings from misidentifying DVD-order episodes; retain manual overrides. 292 tests pass.

## 18.5.0 - 2026-09-07

Native TVDB search/refresh, metadata source setup and aired/DVD order for new TVDB shows. Preserves episode paths/statuses and rejects changed identities. 291 tests pass; synthetic browser add flow verified. Live credentials and remaining parity work outstanding.

## 18.4.3 - 2026-09-07

Cached XEM mappings, manual-override precedence and reverse scene matching. Refresh action and daily metadata-triggered refresh. 286 tests pass. Public XEM sample returned 403; live compatibility remains unverified.

## 18.4.2 - 2026-09-07

Six native notification services with event choices, masked credentials and delivery status; NZBGet/Transmission/Deluge polling and handoff validation. 283 tests pass; disabled service setup verified in isolated browser. Full parity/live certification remain incomplete.

## 18.4.1 - 2026-09-07

Saved new-show defaults and preview/confirm existing-library rename, including sidecars, multi-episode files, conflict guards, rollback and recovery journals. Shared file-operation lock. 269 tests pass and isolated browser workflow verified. Full parity remains incomplete.

## 18.4.0 — 2026-09-07

SickChill audit and per-show preferences: correct profile IDs, language/default statuses, subtitles and numbering search, flat naming, UTC scheduler leases and magnet hashes. 260 tests pass. Full parity remains incomplete; see docs/SICKCHILL_PARITY_AUDIT.md and release notes.

## v18.3.3 — Library Locations and Processing Review

- Manage library roots: add, edit unused paths, set default, remove unused paths.
- Block removal/replacement when shows use a path; list affected shows for reassignment.
- Add Show and Edit Library Folder use configured roots and preview destinations.
- Edit show destinations, optionally updating stored episode paths for files already moved.
- Direct Library editor, reviewed-file approval controls, and unmatched/blocked explanations.
- Free/total disk space with background checks and unavailable status.
- Compact database sizes in KB/MB/GB.
- Restart TV Manager to activate backend changes, then refresh the browser.

Configuration changes do not move or delete media files. Reassign shows before replacing a root they use. Source releases now include a version bump, notes, GitHub push and version tag per iteration.

## v18.3.2 - Post-Processing Safe Show Matching Hotfix

- Fixed post-processing rename matches so short/common show names are not matched from inside longer titles.
- Prevents `Friends.from.College` from being renamed into the show `FROM`.
- Prevents `Friends ... Where Rachel...` from being renamed into the show `ER`.
- Matching now uses the release title prefix before SxxEyy/1xYY instead of arbitrary substring matching.
- One-word/short shows such as `FROM`, `ER`, `YOU`, or `IT` must match the exact show-title prefix.
- Preview results now display show-match confidence/reason before processing.
- Added docs/RELEASE_NOTES_v18.3.2.md.

## v18.3.1 - Global Specials Missing/Wanted Control

- Added one-place global Season 00 / Specials control.
- S00/Specials are hidden from Missing/Wanted and queue status by default.
- Added preview, background ignore/include jobs, and search guard.
- Added docs/RELEASE_NOTES_v18.3.1.md.


## v18.2.6 — Real No-Wait Show Detail Hotfix

- Show Detail now renders a usable screen immediately instead of showing an endless animated loading bar.
- Episode first-page loading uses an explicit short timeout and smaller first load.
- Added stronger Retry / Jobs / Logs fallback when SQLite is busy or blocked.



## v18.2.1 - Show Load Progress Polish
- Added visible loading/progress indicators while opening a show from Show Queue.
- Added Show Detail header progress while show metadata, season counts, and episode rules load.
- Added episode-table progress row while episodes are loading or filters refresh.
- Added an indeterminate progress style for operations that are actively waiting on API/database responses.


## v18.2.0 — Bulk Episode Management & Ignore Rules

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

# Changelog

## v17.21.0 — SQLite Lock Guard + Media Server Maintenance

- Added SQLite writer serialization and longer busy timeout to prevent background scheduler/database lock crashes.
- Added retry-safe scheduler finish and logging updates.
- Added full edit/delete maintenance for media servers and other Advanced configuration records.
- Added background job monitoring for media server test, refresh and watched-sync operations.
- Improved downloader handoff failure reporting.


## v17.19.0 — Downloader Validation Center

- Added `/download-center` for downloader readiness, connection tests, queue polling, and handoff monitoring.
- Added background job APIs for downloader connection tests and queue polling.
- Added accepted search-result handoff candidates with Send action.
- Clarified Launchpad "replacement readiness" loading/meaning and failure behavior.

## 17.13.3 - Windows EXE Robocopy Quoting Patch

- Fixed Windows EXE staging when the project path contains spaces.
- Replaced ROBOCOPY `Start-Process -ArgumentList` call with direct PowerShell argument-array execution.
- Prevents paths like `C:\Acuityware TV Manager` from being split into incorrect source/destination/file arguments.
- Kept EXE staging outside the project tree and final output under `release\windows\TVManager`.
- Updated Windows installer metadata to 17.13.3.

## 17.13.2 - Windows EXE Build + Database Safety

- Prevented Windows EXE packaging from opening or repairing the live `tvmanager.db` during PyInstaller analysis.
- Added SQLite quick-check protection before startup schema repair.
- Added clear database recovery guidance for malformed/corrupt SQLite databases.
- Updated `run.ps1` to use the project virtual environment Python consistently and stop before app import when DB safety fails.



## 17.13.1 - Windows EXE Build Script Safety

- Fixed recursive Windows EXE build script staging that could create nested `dist/TVManager/dist/TVManager` paths.
- Windows EXE builds now stage outside the app tree and publish to `release/windows/TVManager`.
- `build-exe.ps1` now uses the project virtual environment and installs PyInstaller when missing.
- Runtime data, secrets, imports, logs, diagnostics, backups, databases, build output, and release output are excluded from staging.

- v17.13.0 adds Show Queue drill-down: click a show to open `/show/<id>`, filter/search episodes, and search/download from the episode row.

## v17.13.0 - Full Metadata Refresh + Show Queue Date Fix

- Added full-library metadata refresh from Library Health with preview, background progress, counts, and failed-item details.
- Added full metadata refresh job APIs.
- Fixed Show Queue Next Ep / Prev Ep values so dates are normalized and displayed as readable calendar dates.
- Added full-library metadata refresh documentation.

## v17.12.0 - Trakt Discovery + Show Queue

- Added Trakt.tv discovery for trending, popular, anticipated, watched, played, and search-driven show additions.
- Added a modern SickChill-style Show Queue at `/show-queue` with sortable columns and server-side paging.
- Added `/api/trakt/*` endpoints, `/api/show-queue`, and Trakt credential setup documentation.
- Added Trakt identity columns/indexes and performance indexes for all-shows browsing.

## 17.10.0 - Responsive Fit & Distribution Polish

- Fixed sidebar-era layout fit problems on Import Center and Home/Search.
- Added small-screen Menu toggle for left navigation.
- Added automatic table overflow wrapping for legacy screens.
- Improved long path, command palette, workflow ribbon, form grid, and action toolbar responsiveness.
- Added responsive layout audit documentation and release notes.

# 17.9.1 - TMDb Metadata Authentication Reliability

- Restored metadata refresh reliability after Post Processing workflow changes.
- Added shared TMDb credential handling for both `TMDB_BEARER_TOKEN` and legacy `TMDB_API_KEY`.
- Added fallback to imported/saved SickChill TMDb settings where available.
- Converted TMDb 401/403 failures into clear operator-facing JSON errors.
- Added `/api/metadata/status` to report whether TMDb is configured and where the credential was sourced, without exposing secrets.
- Added regression tests for credential loading, legacy API-key support, unauthorized handling, and metadata batch invocation.



## 17.9.1 - Post Processing Workflow

- Added SickChill-style post-processing folder controls.
- Added configured and override completed-download directories.
- Added selectable preview rows and Process Selected / Process All Approved actions.
- Added post-processing configuration API.
- Hardened responsive layouts for left-sidebar screens.

## 17.9.1 - Large Library Performance and Operator Scale

- Fixed the Library view freeze after large SickChill imports by changing `/api/shows` to server-side pagination.
- The Shows page now loads 100 records at a time and offers a Load More workflow instead of trying to render 39K+ shows at once.
- Added `total`, `limit`, `offset`, `next_offset`, and `has_more` response fields to `/api/shows`.
- Added defensive Library API parsing so HTML/error responses are shown as operator-friendly messages instead of leaving the page stuck at `Showing...`.
- Added performance indexes for show names, status filters, and episode season browsing.
- Added large-library regression tests.

# Changelog

## 17.7.0 - Setup Assistant and Cutover Polish

- Added `/setup-assistant` guided replacement checklist.
- Added `/api/setup/summary` cutover readiness endpoint.
- Added SickChill cutover checklist documentation.
- Added setup/cutover UI polish and navigation link.

## 17.5.0 - Launchpad Experience

- Added a premium `/launchpad` operator home screen.
- Added `/api/launchpad/summary` for readiness, counts and next actions.
- Added replacement readiness score and action-oriented migration/health/cutover cards.
- Added product experience documentation and release notes.
- Continued cohesive professional styling across the app.

# v17.3.1

## 17.3.5 - Import Progress Job Startup Fix

- Fixed asynchronous SickChill import job startup error: `_set_import_job() got multiple values for argument 'job_id'`.
- Corrected the queued-job initialization call so the helper receives the job identifier only once.
- Added regression coverage to prevent the duplicate `job_id` call pattern from returning.


- Added active database verification after SickChill import.
- Added `/api/import/verify` and conservative import-audit recovery for empty Shows results after import.
- Import Center now shows the actual active DB counts after import.


## 17.4.0

- Added Workflow cockpit for end-to-end SickChill replacement operations.
- Added `/api/workflow/summary` readiness endpoint.
- Added operator workflow guidance, polished workflow cards, and migration ribbon.


## 17.2.0

- Added complete SickChill replacement server installation runbook.
- Added production Linux deployment guide with systemd service setup.
- Added `scripts/install-linux-service.sh` for `/opt/tvmanager` deployments.
- Added `server_preflight.py` to validate SickChill database copies, media roots, Python/Git availability, and port conflicts before cutover.
- Added v17.2 release notes and packaging tests.

## v17.1.9

- Added early support route registration module for About, Library Health, Routes, and version APIs.
- Added PowerShell startup route verification so the app will not launch without those URLs.

## 17.1.8

- Added startup database doctor for safe upgrades over older tvmanager.db files.
- run.ps1 now verifies/repairs the DB schema before launching the app.

## v17.1.7
- Fixed startup repair for older databases missing `episodes.status` and `episodes.location`.
- Hardened schema repair so engine startup work runs only after core show/episode columns exist.
- Added regression coverage for very old episode schemas.

## v17.1.4
- Fixed Library Health and About routing with trailing-slash and alternate-path aliases.
- Added server-rendered Library Health fallback page so the route shows a support page even if the template/static JavaScript fails.
- Added alternate health-report API path `/api/library-health/report`.
- Preserved visible version footer and About/version support endpoints.


## v17.1.3

- Fixed About page reliability with server-rendered version/build details.
- Added `/api/about` endpoint.
- Publicly exposed `/about`, `/api/version`, and `/api/about` for local support verification.
- Added tests for About page route, visible version and API payload.

## v17.1.1

- Added visible app version footer across TV Manager pages.
- Added About page for build/support verification.
- Added `/api/version` endpoint.
- Updated System page to show the runtime version from the VERSION file.

# TV Manager v17.0

## Added
- SickChill import analysis endpoint: `/api/import/sickchill/analyze`.
- SickChill dry-run preview endpoint: `/api/import/sickchill/preview`.
- Idempotent v17 SickChill importer with IMDb normalization and repeat-run duplicate protection.
- `legacy_identity_map` table for source-to-TV-Manager show identity tracking.
- `import_run_details` audit table for per-show and per-episode migration decisions.
- Duplicate candidate API: `/api/library/duplicates`.
- Manual bounded metadata refresh API: `/api/metadata/refresh/run`.

## Changed
- `/api/import/sickchill` now uses the v17 importer while keeping the existing upload contract.
- Repository version advanced to `17.0`.

# Changelog

## 17.7.0 - Setup Assistant and Cutover Polish

- Added `/setup-assistant` guided replacement checklist.
- Added `/api/setup/summary` cutover readiness endpoint.
- Added SickChill cutover checklist documentation.
- Added setup/cutover UI polish and navigation link.

## v17.1.6

- Fixed startup crash on older databases missing `shows.imdb_id`.
- Startup schema repair now adds `imdb_id` before creating `idx_shows_imdb`.
- Added regression coverage for the `no such column: imdb_id` failure path.


## 17.1
- Added Import Center analyze → preview → import browser workflow.
- Added Library Health dashboard for post-import checks, metadata gaps, missing files, duplicate groups, and recommendations.
- Added safe duplicate cleanup preview/apply endpoints with managed-trash moves and audit trail.
- Added v17.1 migrations, tests, release notes, and documentation.


## 16.0
- Added optional browser administrator login with PBKDF2 password hashing.
- Added CSRF protection for authenticated browser write requests.
- Added failed-login throttling and security event history.
- Blocked anonymous LAN access and guarded non-loopback Waitress binding.
- Preserved bearer-token integrations and added API access auditing.
- Added Naming settings UI with presets and live multi-episode preview.
- Enabled scheduled post-processing only when SickChill process_automatically is enabled and Simulation Mode is off.
- Implemented real rate-conscious scheduled metadata refresh with per-show state.
- Improved existing-library scanning for multi-episode files.
- Hardened Waitress checks in PowerShell startup scripts.

## 15.0.1
- Added canonical fresh-Windows-PC installation and migration guide.
- Documented PowerShell execution policy, Waitress repair, production startup, status checks, UNC path considerations, firewall/LAN cautions, upgrades and troubleshooting.
- Hardened setup.ps1 with Python preflight, dependency verification, .env preservation and clear next-step output.
- Added fresh-install documentation to release and CI checks.

## 15.0
- Implemented SickChill-compatible naming tokens in live post-processing.
- Added multi-episode naming and Windows-safe filename sanitization.
- Added associated subtitle/NFO/artwork renaming and movement.
- Added content fingerprints and duplicate-content scanning.
- Added cross-process scheduler leases and stale-run recovery.
- Added richer post-processing preview and scheduler lease visibility.
- Added optional Waitress production runner and Windows startup task.
- Expanded automated validation to naming, fingerprints and scheduler recovery.

## 14.0
- Unified acquisition lifecycle and event history for episode and season-pack downloads.
- Safe upgrade staging with automatic rollback and downgrade prevention.
- Targeted Plex path scans after imports with safe whole-library fallback for other media servers.
- Subtitle language preferences imported from existing settings plus retry backoff.
- Unified Queue for episodes and season packs with lifecycle history.
- Upgrade replacement history and one-click rollback.
- Operations summary now surfaces active and attention-required acquisitions.

## 13.0.1
- Fixed Windows startup failure caused by missing `dbcore` imports in modules that use the centralized database layer.
- Added a release audit to verify every `dbcore.` reference has a matching import.

## 13.0
- SQLite WAL/busy-timeout reliability and versioned migrations.
- Fixed nested writer lock paths.
- Persistent scheduler runs.
- Season-pack episode/progress correlation.
- qBittorrent magnet hash tracking.
- Multi-episode post-processing.
- Guarded Proper/Repack searching/grabbing.
- Watched-sync UI/runtime fixes.

## 12.0
- Plex/Jellyfin/Emby watched-state sync.
- Subtitle job queue.
- Proper/Repack review candidates.
- Mapping-source registry foundation.

## 11.0
- Functional season-pack grab workflow.
- Optional API bearer-token security.
- Unit tests and release validation.
- GitHub Actions CI.
- Comprehensive documentation set.

## 10.0
- Season-pack provider searching.
- OpenSubtitles-compatible acquisition.
- Quality upgrade planner.
- Backup validation and redacted diagnostics.
- Windows startup installer.

## 9.0
- Retention execution with managed trash.
- Watched-state storage.
- System health and API catalog.

## 8.0
- Global command palette, queue triage, dashboard insights, tags/favorites, retention framework, season-pack planning.

## 7.0
- Provider circuit breakers, explainable decisions, automation rules, simulation mode, configuration snapshots, path/conflict diagnostics.

## 6.x
- Custom Newznab/Torznab, NZBGet/Transmission/Deluge, scene/anime mappings, show groups, webhooks, media-server integration, subtitle audit.

## 5.x
- Quality profiles, dashboards, generic imported-settings editor, downloader polling, metadata/NFO/artwork.

## 4.x
- Search engine, SAB/qBittorrent handoff, scheduler, post-processing, missing/upcoming/activity, library scans.

## 3.x
- SickChill database/config migration, manager redesign, metadata refresh.

## 1–2
- TMDb/IMDb search and initial SQLite TV library.


## 17.3.4 - SickChill Import Database Reliability

- Fixed database lock failures after SickChill import by restructuring the importer transaction lifecycle.
- The importer now reads the SickChill source completely, closes it, repairs/verifies the target TV Manager schema, then performs a bounded target write transaction.
- Added explicit commit/rollback/finally handling and immediate post-import visibility verification from a brand-new read-only connection.
- Added WAL/busy-timeout hardening and passive checkpoint handling after successful import.
- Import Center responses now include target visibility counts so operators can confirm shows and episodes landed in the active `tvmanager.db`.
- Added regression tests for post-import write access and immediate show visibility.

## 17.3.1 - Product experience refresh

- Refreshed the application look and feel with a cohesive professional operations-console design.
- Added active navigation highlighting and more consistent page hierarchy.
- Added product hero sections to key workflows: Dashboard, Shows, Import Center, Library Health and About.
- Improved visual consistency for panels, cards, tables, forms, buttons, empty states and version footer.
- Added UI design system documentation.


## 17.7.0 - Left Navigation + Distribution Readiness

- Replaced crowded top navigation with a categorized left sidebar.
- Added cross-platform installation guide.
- Added Windows EXE installer build documentation and starter scripts.
- Added navigation design documentation.

## v17.14.0 — Database Protection + Progress Polish

- Added Database Safety Center at `/database-safety`.
- Added verified SQLite backups using the SQLite backup API, with quick-check validation and SHA-256 records.
- Added redacted configuration snapshots so `.env` and runtime settings are protected without exposing secrets.
- Added backup manifest tracking under `backups/db-backup-manifest.json`.
- Added shared progress job APIs and converted Library Health scanning to a progress-bar workflow.
- Added `protect_db.py` for command-line backup and backup inventory scans.
## 17.15.0 - Background Jobs, Scheduler, Metadata Art Polish

- Added Active Jobs screen for background/multithreaded work.
- Added scheduled missing metadata, artwork, Library Health and database protection jobs.
- Added progress-bar job mode for show metadata refresh, episode search and post-processing.
- Added episode artwork metadata fields and missing metadata refresh APIs.



## 17.16.0 - SickChill Parity Manage Center

- Added `/manage` as a modern replacement for SickChill Manage workflows.
- Added backlog overview, episode status management, failed downloads, missed subtitles, scene exceptions and mass refresh.
- Added background-job progress for long-running manage actions.
- Updated navigation, command palette, docs and tests.


## v17.18.0 - Progress Everywhere + Professional Logs

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



## v18.2.4 — No-Hang Show Detail Hotfix

- Show Detail no longer waits for season counts before rendering the show header.
- Added `/api/shows/<id>/seasons-fast` so season filters appear from distinct season values first.
- Episode list first page now uses lean columns and a shorter UI timeout so it fails fast instead of appearing stuck.
- Detailed season/count refreshes run after the page is usable and never block first paint.
- Local Flask fallback server now runs threaded with debug disabled for better UI responsiveness during scans.
- Read-only SQLite UI requests now fail faster when background work blocks the database, allowing retry/log guidance instead of hanging.

## v18.2.3 — Fast Show Open & Subtitle Scan Guard
- Show Detail now opens the core show record first and loads expensive counts after the screen is usable.
- Episode list paging uses quick fetch plus one-row lookahead instead of blocking on full count queries.
- Episode API selects only UI-required columns for faster loads.
- Subtitle scans now cap candidates and skip network paths by default to prevent NAS/SMB hangs.
- Added fast episode indexes for show detail and episode-management filters.

## v18.2.2 — Fast Loading Hotfix

- Prevents subtitle scans from holding the database writer lock for the entire scan.
- Adds batched subtitle status writes and a scan safety time limit.
- Makes Show Detail loading use read-only, fast-fail database access.
- Adds a user-visible timeout message when show loading is blocked by background work.


## v18.2.5 — Show Detail No-Wait Hotfix

Show Detail now uses no-wait snapshot and episode-lite endpoints for first paint. A hard browser watchdog replaces indefinite loading spinners with Retry, Jobs, and Logs actions when the database is busy.


## v18.3.0 - SickChill Parity Audit and Online Help

- Added in-app Help Center at `/help`.
- Added SickChill parity matrix and product workflow map.
- Added contextual guides for Show Queue, Episode Management, Ignore Rules, Download Center, Post Processing, Subtitles, and Troubleshooting.
- Added Help Center link to Administration navigation and footer.
- Added help APIs for future contextual help/tooltips.
