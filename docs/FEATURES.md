# Feature Catalog

## Migration
- SickChill SQLite database import with legacy JSON preservation.
- SickChill `config.ini` import including provider/client/settings preservation.
- Existing media library indexing.
- Automatic additive schema migration and pre-upgrade backups.

## Search & Providers
- Newznab and custom Newznab.
- Torznab.
- Recent and backlog searches.
- Manual episode search.
- Season-pack search and grab.
- Provider ordering, randomization, categories and minimum seeders.
- Provider health, latency, success rate, circuit breaker and exponential cooldown.
- Search-result de-duplication.
- Explainable scoring and configurable automation rules.
- Preferred, required and ignored words.
- Multi-episode parsing.

## Download Clients
- SABnzbd.
- NZBGet.
- qBittorrent.
- Transmission.
- Deluge.
- Blackhole.
- Downloader connection tests and polling where implemented.
- Failed-release retry workflow.

## Library
- Show/season/episode management.
- Favorites, tags, groups and saved-filter model.
- Upcoming and Missing views.
- Scene numbering and aliases.
- Anime absolute numbering.
- Existing-library scans.
- Duplicate/conflict detection.
- Remote-to-local path mappings.
- Quality profiles and upgrade planner.
- Season-pack planning.

## Post-processing
- Move/copy/hardlink workflows.
- Season folders.
- Existing file/status reconciliation.
- Media-server refresh after processing.
- NFO and artwork generation.
- Safe managed-trash retention workflow.

## Subtitles
- Local subtitle audit.
- SRT/ASS/SSA/SUB/VTT detection.
- OpenSubtitles-compatible provider configuration.
- Episode subtitle search/download and sidecar placement.

## Media Servers / Notifications
- Plex, Jellyfin, Emby and Kodi connection/refresh support.
- Event webhooks.
- Imported legacy notifier settings remain available.
- SMTP test support.

## Reliability & Safety
- Simulation mode.
- Configuration snapshots and transactional restore.
- Database ZIP backups and integrity validation.
- Provider health/circuit breakers.
- Root-folder reachability/writeability checks.
- Diagnostic bundles with secret redaction.
- Episode locks.
- Retention preview before apply.
- Managed trash rather than permanent delete.
- Windows startup task installer.

## Security
- Localhost-first deployment.
- Optional API token enforcement.
- API tokens stored as SHA-256 hashes.
- Secret masking in UI and diagnostics.

## v12 additions
- Plex watched-state import.
- Jellyfin/Emby watched-state import.
- Automated subtitle job queue with retry state.
- Proper/Repack review candidates.
- Mapping-source registry foundation for XEM/AniDB automation.

## v13 additions
- WAL/busy-timeout database reliability layer.
- Versioned migrations and online pre-migration backup.
- Scheduler run history.
- Exact qBittorrent magnet-hash correlation.
- Season-pack episode linkage and completion tracking.
- Multi-episode post-processing across every episode in a file.
- Guarded Proper/Repack provider search and grab.
- Media-server watched-sync UI action.

## v14 additions
- Acquisition state machine with persistent transition history.
- Unified episode/season-pack queue.
- Safe upgrade staging, downgrade prevention and rollback.
- Targeted Plex path scanning after imports.
- Subtitle preferences and exponential retry backoff.
- Acquisition attention metrics in Operations.

## v15 additions
- SickChill-compatible naming engine used by post-processing.
- Multi-episode naming and Windows-safe sanitization.
- Associated sidecar rename/move support.
- Cached content fingerprints and duplicate-content Operations scan.
- Cross-process scheduler leases and abandoned-run recovery.
- Optional Waitress Windows production runner.

## v16 additions
- Optional administrator browser login and LAN access guard.
- CSRF protection and failed-login throttling.
- Security event and bearer API access auditing.
- Naming presets and live Settings preview.
- Live gated scheduled post-processing.
- Real stale-show metadata batch refresh.
- Multi-episode existing-library scanning.
