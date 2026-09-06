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
