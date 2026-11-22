# Movies

TV Manager finds, downloads and organizes movies with the setup you already use for TV: the same indexers, download clients, TMDb credential and Plex servers. Open **Movies** in the side menu (Library section).

## What runs by itself

Four scheduled jobs appear on the Jobs page. They run whenever TV Manager automation is on (Settings › Automation):

| Job | Every | What it does |
|---|---|---|
| `movie_library_scan` | 24 hours | Builds the complete list of movies you own (see below) so nothing you own is downloaded again. Also detects the movie library folder from Plex. |
| `movie_discovery` | 12 hours | Asks TMDb for movies released on digital or disc in your region within the last 120 days that pass your filters (rating, votes, original language, skipped genres) and adds up to 10 new ones per run as Wanted. |
| `movie_search` | 1 hour | Searches up to 10 wanted movies per run on your indexers and sends the best release to your download client. New movies are searched every 6 hours for two weeks, then daily. Movies TV Manager downloaded below the "Upgrade until" resolution are searched weekly for a better copy. |
| `movie_downloads` | 10 minutes | Asks the download clients about every movie download, imports completed ones into the library, and retries failed or stalled ones. |

Discovery and search never run before the first library scan has finished.

## The complete owned-movie list

The library scan reads, every day and on **Scan library now**:

1. **Every movie library on every enabled Plex server** (Settings › Media Servers), page by page so very large libraries are read in full. TMDb and IMDb IDs from Plex are used for matching, including older Plex agents.
2. **Every folder behind those Plex libraries** that the TV Manager server can reach (with Path Mappings applied), plus the movie library folder and any **Other movie folders** listed under Movies › Settings, one per line. This catches movies on disk that Plex has not matched or does not know about.

On disk a movie is a `Title (Year)` folder (also `Title [Year]` or a release-style name with a year), a loose video file in the folder, or such a folder one level down inside a grouping folder (`Movies\A\…`, `Movies\Action\…`). Hidden, trash and NAS system folders are skipped; a folder inside another listed folder is read once. A movie found in several places counts once (TMDb ID, then IMDb ID, then title and year).

**What the last library scan read** (Movies › Settings) lists every Plex server and library, every folder, how many movies each gave, and any problem. If a Plex server or library cannot be read, automatic adding of new movies is paused until a scan reads everything, because owned movies there would be unknown. A Plex folder that this server cannot reach is not a problem: Plex already listed its movies. A listed folder that cannot be reached is shown as a problem.

## Searching

- Indexers: every enabled Newznab provider (when an NZB client is set) and every enabled Torznab provider (when a torrent client is set). Provider health and suspension are shared with TV searches.
- Movie categories (default `2000`) instead of the TV categories saved on the provider.
- IMDb ID search first (`t=movie&imdbid=`); indexers that do not support it are remembered and searched by `Title Year` instead.
- A release must be the movie: the title before the year must match the movie title (or original title, with or without a leading "The", `&` = `and`) and the year must be within one year. TV episodes (`SxxEyy`) are rejected.
- Rejected automatically: cinema camera and screener copies (CAM, TS, TC, SCR, R5…), disc images (ISO, BDMV, COMPLETE BLURAY), 3D, remux (unless allowed), HEVC (if turned off), outside the resolution range (default 720p–1080p), outside the size range (default 500 MB – 40 GB), global or movie ignore words, torrents without seeders, and previously failed releases.
- Score: resolution, then source (Blu-ray > WEB-DL > WEBRip > HDTV), proper/repack, preferred words, seeders, indexer priority.

## Download clients

| Protocol | Client | Category / label |
|---|---|---|
| NZB | SABnzbd | `movies` (SABnzbd uses its default category if it has no `movies` category) |
| NZB | NZBGet | `movies` |
| Torrent | qBittorrent | category `movies` |
| Torrent | uTorrent / BitTorrent (uTorrent Web UI) | label `movies` |
| Torrent | Transmission, Deluge, rTorrent, Download Station, put.io, blackhole | as for TV |

## Failed and stalled downloads

A download the client reports as failed, or that is not complete after 36 hours ("Give up on a download after"), is marked Failed, its release is blocklisted and the movie is searched again on the next run. A client that cannot be reached is not treated as a stall. **Try another release** on the Downloads tab does the same by hand.

## Importing

- The completed files are found from the client (SABnzbd storage folder, qBittorrent content path, uTorrent save path) or by release name in the download folders: the optional Movies download folder, the TV completed-downloads folder, the torrent folder and SABnzbd's complete and category folders. Path mappings apply.
- The largest video (samples skipped) becomes `<library>\Title (Year)\Title (Year).ext`; subtitles next to it are kept (`.en.srt` etc.).
- Usenet downloads are moved and the leftover release folder is deleted. Torrents are hardlinked by default so they keep seeding (copied if the library is on another drive); this can be set to copy or move.
- An upgrade moves the old file to the trash on the movie share (`.tvmanager-trash\upgrades\`), restorable from the Trash page.
- Every enabled Plex server scans the movie folder (other media servers refresh their library).
- Simulation mode previews imports without moving anything and does not send downloads.

## Settings

Movies › Settings: automation on/off, library folder (empty = detected from Plex), completed-downloads folder, torrent import method, discovery filters, quality limits, give-up hours, ignore/preferred words, client categories/labels and indexer movie categories. Folders are checked when saved.

## API

`GET /api/movies?status=&q=&sort=&page=`, `POST /api/movies {"tmdb_id":…}`, `GET /api/movies/summary`, `GET /api/movies/discover?list=digital|trending|popular|now_playing|upcoming|top_rated&q=&page=`, `GET|POST /api/movies/settings`, `GET /api/movies/downloads`, `POST /api/movies/downloads/<id>/fail`, `GET|POST /api/movies/<id>` (`{"status":"Ignored"|"Wanted"}`, `{"monitored":…}`), `POST /api/movies/<id>/search {"auto_grab":true}`, `POST /api/movies/results/<id>/grab`, `POST /api/movies/jobs/<job>/run`.
