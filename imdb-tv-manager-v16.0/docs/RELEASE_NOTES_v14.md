# TV Manager 14.0 Release Notes

## Acquisition control
- Added explicit acquisition lifecycle events.
- Unified episode and season-pack Queue.
- Added lifecycle history per Queue item.
- Manual Fail & Retry now participates in lifecycle history.

## Safer upgrades
- Existing files are staged in managed trash before replacement.
- Recognized quality downgrades are blocked.
- Same-quality replacements must be corrective PROPER/REPACK releases.
- Failed imports attempt automatic rollback.
- Completed replacements can be rolled back from the Upgrades page.

## Media servers
- Plex post-import scanning can target the show path rather than scanning every Plex library.
- Jellyfin/Emby retain safe whole-library refresh fallback until item-level matching is fully validated.

## Subtitles
- Scheduler automatically queues missing subtitles using imported subtitle language preferences when available.
- Failed subtitle jobs use exponential retry backoff instead of retrying every scheduler cycle.
- Provider/language choice is recorded on jobs.

## Operations
- Operations dashboard surfaces active acquisitions and items that need attention.
