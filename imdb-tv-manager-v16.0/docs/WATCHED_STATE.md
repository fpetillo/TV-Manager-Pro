# Watched-State Synchronization

TV Manager stores watched state per episode and profile.

## Jellyfin / Emby
Sync reads episode user data including `Played` and `PlayedPercentage`. Matching prefers media path, then series/season/episode.

## Plex
Sync reads user-specific episode metadata. `viewCount` indicates watched state; `viewOffset` and `duration` represent in-progress playback.

## Safety
Sync updates TV Manager metadata only; it never writes watched state back to the media server.
