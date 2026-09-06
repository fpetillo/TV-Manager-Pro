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
