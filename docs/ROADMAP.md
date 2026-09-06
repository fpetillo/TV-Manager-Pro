# Roadmap

## Completion targets retained
- Watched-state synchronization from Plex/Jellyfin/Emby.
- Automatic XEM mapping retrieval.
- Deeper AniDB/anime matching.
- DVD-order metadata translation.
- Stronger Proper/Repack automated upgrade workflow.
- Downloader-specific season-pack completion correlation.
- Additional subtitle providers and automatic subtitle scheduling.
- Production WSGI packaging and TLS/reverse-proxy deployment recipes.
- Broader integration tests with mocked provider/downloader APIs.
- Mobile/PWA client and authenticated remote dashboard.
- Recommendation/discovery engine that remains separate from automatic acquisition decisions.

## v12 follow-on
- XEM retrieval adapter once a stable supported endpoint is selected.
- AniDB mapping adapter and DVD-order translation.
- Automatic Proper/Repack searches and guarded grabs.
- Per-user watched-state profile selection UI.
- Downloader-specific season-pack completion correlation.

## After v13
- Stable XEM/AniDB mapping retrieval adapters after endpoint verification.
- DVD-order translation.
- True Windows service packaging in addition to Task Scheduler.
- Targeted media-server refresh by series/library.
- Exact IDs for non-magnet qBittorrent additions.
- Mocked integration tests for SAB, qBittorrent, Newznab/Torznab, Plex and Jellyfin.
- Production WSGI deployment plus CSRF/session hardening.

## After v14
- Exact Jellyfin/Emby item-level post-import refresh after stable provider-ID/path matching validation.
- XEM/AniDB/DV-order mapping adapters.
- True Windows service packaging and production WSGI server.
- Stronger web authentication/CSRF and encrypted-at-rest integration secrets.
- Full downloader/provider integration mocks and end-to-end browser tests.

## After v15
- XEM/AniDB and DVD-order mapping adapters with verified current endpoints.
- Exact Jellyfin/Emby targeted post-import refresh.
- Full authentication/CSRF hardening for LAN exposure.
- Download-client integration mocks and browser-driven end-to-end testing.
- Smarter naming presets/editing UI and filename collision policy controls.

## After v16
- XEM/AniDB/DVD-order mapping adapters.
- Exact Jellyfin/Emby targeted post-import refresh.
- Password reset/recovery workflow with explicit local-console authorization.
- Optional HTTPS/reverse-proxy deployment guide.
- Download-client/provider mocks and full browser end-to-end tests.
- Fine-grained roles if multi-user administration becomes necessary.
