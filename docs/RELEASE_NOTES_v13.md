# TV Manager 13.0 Release Notes

## Reliability
- Centralized WAL/busy-timeout SQLite layer.
- Versioned schema migration history.
- Online pre-v13 database backup and post-migration integrity check.
- Fixed nested SQLite writers in search-decision and SAB completion logging.
- Persistent scheduler run history.

## Acquisition
- qBittorrent magnet hash capture for exact polling when the source is a magnet URI.
- Season-pack downloads link to every covered episode.
- SAB and qBittorrent season-pack progress correlation.
- Season packs complete only after every linked episode is imported.

## Post-processing
- Multi-episode files such as `S01E01E02` update every matching episode.
- Post-processing now carries show/episode IDs into its action record.

## Upgrades
- Proper/Repack review can perform a real provider search.
- Grabbing is explicit and blocked while Simulation Mode is enabled.
- A later Accept automation rule can no longer silently erase an existing rejection.

## Media and subtitles
- Fixed Plex/Jellyfin/Emby watched-sync media-server schema mismatch.
- Added Sync Watched to the Media Servers UI.
- Subtitle and watched-sync jobs are first-class scheduler jobs.
