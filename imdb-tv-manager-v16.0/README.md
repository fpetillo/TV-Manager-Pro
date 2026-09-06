# TV Manager

**Current version: 17.0**

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
