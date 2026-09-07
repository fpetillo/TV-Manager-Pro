# SickChill coverage audit — 2026-09-07

Full parity is not achieved. This audit replaces earlier broad claims of completeness. Complete means the named local workflow exists; it does not certify an external integration. Partial identifies implemented behavior plus missing coverage. Missing means no complete corresponding workflow was identified.

Sources: [official feature list](https://sickchill.github.io/), [show settings](https://github.com/SickChill/sickchill/wiki/Show-settings-explained), [settings](https://github.com/SickChill/sickchill/wiki/Settings-explained).

Upstream source tree: `e1f8475ded8dd77662fad3ba9488740133ca8ce1`. The adjacent JSON preserves the checked adapter paths. This is a feature-family audit and adapter inventory, not a claim of exhaustive behavioral equivalence.

| Area | Capability | Location | Status | Evidence / remaining work |
|---|---|---|---|---|
| Shows | Configured storage roots and free space | Library Locations | Complete | library_locations.py, library_storage.py: add/default/remove unused roots; protect roots used by shows. |
| Shows | Choose destination when adding shows | Search / Trakt | Complete | show_destination.js: configured root chooser and destination preview. |
| Shows | Edit show folder and preferences | Show Detail / Library | Complete | show_preferences.py: typed profile IDs, pause, language, statuses, subtitle and numbering options. |
| Shows | Browse shows and episodes | Show Queue / Show Detail | Complete | manager.js, show_detail.js: paging, filtering and episode detail. |
| Shows | Import SickChill library | Import Center | Partial | sickchill_importer.py: imports show/episode data; not every upstream configuration field is translated. |
| Shows | Save add-show preferences as defaults | Edit Show Settings / Add Show | Complete | show_preferences.py: save defaults without changing existing shows; Search and Trakt add routes inherit them. |
| Episodes | Bulk episode status management | Manage Center | Complete | episode_rules.py and sickchill_parity.py: preview/apply episode changes. |
| Episodes | Specials / Season 00 control | Show Detail / Settings | Complete | episode_rules.py: ignored specials excluded from search and missing counts. |
| Search | Manual and backlog episode search | Show Detail / Missing | Partial | engine.py: search and scoring implemented; live provider behavior needs validation. |
| Search | Date, sports and scene searches | Show Settings / Advanced | Partial | show_preferences.py: date and stored scene numbering used in provider requests; manual and cached XEM mapping sources are supported. |
| Search | Anime and automatic XEM mapping | Advanced | Partial | scene_sync.py: cached XEM refresh after metadata refresh, manual override precedence and reverse matching. Live XEM returned HTTP 403 in this environment; aliases/group rules and complete multi-mapping search remain partial. |
| Search | Native SickChill provider roster | Providers | Partial | Generic Newznab/Torznab adapters do not implement upstream site-specific login, cookies and scraping. See upstream inventory. |
| Downloads | Client handoff and queue monitoring | Download Center | Partial | engine.py and downloader_polling.py: SAB/qBittorrent plus NZBGet/Transmission/Deluge polling. Other upstream clients remain missing. Live credentials/clients needed for end-to-end checks. |
| Downloads | Failed download history and retry | Manage Center | Partial | Failure records and retry workflows exist; automatic recovery needs live client validation. |
| Post processing | Preview and approve completed files | Post Processing | Complete | engine.py: matched/blocked/unmatched review and explicit approval before processing. |
| Post processing | Naming and season folders | Naming / Show Settings | Complete | naming.py: configured naming and per-show flat/season folders. |
| Post processing | Archive extraction and extra scripts | Post Processing | Missing | No complete SickChill-compatible archive extraction and post-processing script workflow. |
| Post processing | Rename existing library in place | Show Detail / Library | Complete | library_rename.py: signed preview, selected approval, no overwrite, sidecars, multi-episode grouping, rollback and recovery journals. |
| Metadata | TMDb refresh and language | Show Settings | Partial | metadata_service.py: per-show language and default new-episode statuses; requires TMDb configuration. |
| Metadata | TVDB / AniDB as primary indexers | Metadata | Missing | Imported IDs are preserved but native TVDB/AniDB metadata providers are not implemented. |
| Metadata | DVD episode ordering | Show Settings | Missing | No alternate DVD-order metadata workflow. Upstream wiki also notes TVDB API limitations. |
| Metadata | NFO and artwork format coverage | Metadata | Partial | Metadata/artwork routines exist; full upstream format and consumer compatibility are not verified. |
| Subtitles | Automatic subtitle search and per-show switch | Subtitles / Show Settings | Partial | sync.py and production.py: OpenSubtitles adapter and per-show opt-out; upstream subtitle-provider coverage is incomplete. |
| Notifications | Native notification services | Notification Services | Partial | notifiers.py: native Discord, Slack, Telegram, Gotify, Pushover and Pushbullet event delivery. Other upstream adapters remain missing; live delivery is unverified. |
| Media servers | Plex / Kodi / Emby / Jellyfin updates | Media Servers | Partial | Configuration and refresh integrations require live server validation; not all upstream behaviors are covered. |
| Automation | Scheduled jobs and mutual exclusion | Jobs / Settings | Partial | scheduler_guard.py: UTC leases and atomic acquisition; every scheduled external workflow is not yet certified. |
| Operations | Logs, job status and diagnostics | Logs / Jobs / System | Complete | Local status, progress and diagnostic workflows implemented. |
| Safety | Backup and restore | Database Safety | Partial | Backup validation and recovery guidance exist; native complete restore workflow is missing. |
| Help | In-app workflow guidance | Help Center | Complete | help_content.py: searchable guides and explicit coverage gaps. |

## Upstream integration inventory

Each entry below requires its own adapter and live compatibility check. A generic webhook or Torznab endpoint is not evidence of native compatibility. Upstream files may themselves refer to discontinued services; inclusion is not a recommendation to use them.

| Upstream adapter | TV Manager verification |
|---|---|
| `sickchill/oldbeard/clients/deluge.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/clients/deluged.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/clients/download_station.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/clients/mlnet.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/clients/putio.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/clients/qbittorrent.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/clients/rtorrent.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/clients/transmission.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/clients/utorrent.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/boxcar2.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/discord.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/emailnotify.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/emby.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/freemobile.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/gotify.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/growl.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/jellyfin.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/join.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/kodi.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/libnotify.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/matrix.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/mattermost.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/mattermostbot.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/nmj.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/nmjv2.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/plex.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/prowl.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/pushalot.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/pushbullet.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/pushover.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/pytivo.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/rocketchat.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/slack.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/synoindex.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/synologynotifier.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/telegram.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/trakt.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/tweet.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/notifiers/twilio_notify.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/abnormal.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/alpharatio.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/archetorrent.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/binsearch.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/bitcannon.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/bjshare.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/btn.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/cpasbien.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/danishbits.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/demonoid.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/elitetorrent.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/eztv.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/filelist.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/gimmepeers.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/hd4free.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/hdbits.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/hdspace.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/hdtorrents.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/hdtorrents_it.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/horriblesubs.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/hounddawgs.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/ilcorsaronero.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/immortalseed.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/iptorrents.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/kat.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/limetorrents.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/magnetdl.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/morethantv.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/ncore.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/nebulance.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/newpct.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/newznab.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/norbits.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/nyaa.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/omgwtfnzbs.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/pretome.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/rarbg.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/rsstorrent.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/scc.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/scenetime.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/shazbat.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/skytorrents.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/speedcd.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/thepiratebay.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/tntvillage.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/tokyotoshokan.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/torrent9.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/torrent911.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/torrent_paradise.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/torrentbytes.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/torrentday.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/torrentleech.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/torrentproject.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/torrentz.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/tvchaosuk.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/xthor.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/yggtorrent.py` | Native equivalence not certified; see feature family above. |
| `sickchill/oldbeard/providers/zamunda.py` | Native equivalence not certified; see feature family above. |
| `sickchill/providers/GenericProvider.py` | Native equivalence not certified; see feature family above. |
| `sickchill/providers/result_classes.py` | Native equivalence not certified; see feature family above. |
| `tests/sickchill_tests/providers/test_generic_provider.py` | Native equivalence not certified; see feature family above. |
| `tests/sickchill_tests/providers/test_nzb_provider.py` | Native equivalence not certified; see feature family above. |
| `tests/sickchill_tests/providers/test_torrent_provider.py` | Native equivalence not certified; see feature family above. |

## Acceptance work remaining

1. Complete native indexer coverage and automatic numbering synchronization.
2. Implement and test remaining library workflows: complete restore and archive/script processing.
3. Verify each provider, downloader, subtitle service and notifier independently with its configured service.
4. Test the full search → handoff → completion → processing → notification sequence for each supported client.
5. Update this matrix only with implementation and test evidence.

## This iteration validation

269 automated tests passed before release checks; final results are recorded in the release manifest. Isolated browser testing verified Show Settings opens, saves profile ID 4, language fr-FR, Skipped defaults, and disabled subtitles/season folders; reopening preserves them. Production media and configuration were not used for these tests.

18.4.1 isolated browser also verified media/subtitle rename and saving new-show defaults; both add APIs inherited saved preferences.

18.4.2 adds six native notifier adapters and three client pollers, with mocked service tests (283 total passing) and isolated configuration UI verification. Live services remain uncertified; see the release notes for API references and limitations.

18.4.3 adds cached XEM mappings and reverse matching. 286 tests pass; public XEM sample returned HTTP 403, so live compatibility is not verified.
