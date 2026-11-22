# TV Manager v18.26.0 — Movies

Built on v18.25.0 (speed fixes, Missing Episode Autopilot, trash on the media share).

## What changed

TV Manager now manages movies as well as TV, replacing CouchPotato/Radarr-style tools without any extra applications. Movies use the indexers, download clients, TMDb credential and Plex servers already configured for TV.

Open **Movies** in the side menu (Library section):

- **Library**: wanted, downloading, downloaded and ignored movies with posters, quality, size and live download progress. Each movie has Search, Releases (every result with the reason it was rejected, and a Download button) and Ignore/Want.
- **Discover**: new digital and Blu-ray releases that pass your filters, trending, popular, in theaters, upcoming, top rated, or a TMDb title search. **Add** puts a movie on the wanted list; upcoming and in-theater movies wait until they are out on digital or disc.
- **Downloads**: every movie download with client, status, progress and notes, and **Try another release**.
- **Settings**: library folder (detected from Plex when empty), discovery filters, quality, give-up time, client categories/labels, and buttons to run each job now.

Automatically, without intervention:

1. **Library scan** (daily): movies already in your Plex movie libraries or the movie library folder are recorded, so nothing you own is downloaded again. The movie library folder is detected from Plex.
2. **Discovery** (twice a day): movies released on digital or disc in the last 120 days with a TMDb rating of at least 6.5 from 150+ votes, in English, excluding documentaries and TV movies, are added (up to 10 per run). All of these are adjustable.
3. **Search** (hourly): wanted movies are searched on your indexers (IMDb ID first, movie categories) and the best release, 720p–1080p by default with no camera copies, disc images or remuxes, goes to SABnzbd or your torrent client under a `movies` category/label.
4. **Downloads** (every 10 minutes): completed downloads are renamed to `Title (Year)\Title (Year).ext` in the library (Usenet moved and cleaned up, torrents hardlinked so they keep seeding) and every Plex server scans the new folder. Failed downloads, and downloads not finished after 36 hours, are blocklisted and another release is searched.

Details: [MOVIES.md](MOVIES.md).

## Requirements

- TV Manager automation must be on (Settings › Automation) for the scheduled movie jobs to run. The Movies page says so if it is off.
- TMDb configured (already required for TV metadata).
- A movie library folder reachable from the TV Manager server. It is detected from a Plex movie library location when the path is reachable from the server; otherwise enter it under Movies › Settings.
- BitTorrent/uTorrent needs its Web UI enabled, as for TV.

## Updating to 18.26.0

Download `update-server.ps1` from the v18.26.0 tag and run it, as in [WINDOWS_SERVER_UPDATE.md](WINDOWS_SERVER_UPDATE.md); start TV Manager with run.ps1. The movie tables are created on start; existing data is not changed. Then open **Movies** and read the status line under the counters.

## Validation

- 26 new tests: upgrade import with the old file moved to the share trash (restorable on the Trash page), release-to-movie matching (titles with years, leading "The", `&`, off-by-one year, TV episodes), quality and size rejections and preference, IMDb search with grab and download record, text-search fallback remembered per indexer, blocklist, upgrade search, torrent label, SABnzbd import with Plex naming, subtitles and cleanup, torrent hardlink import, failed/stalled/unreachable-client handling, simulation-mode preview, library scan from Plex and folders, discovery filters and limits, digital-release wait and search back-off, settings validation, job registration, and the page and API in the running app.
- Browser QA on a disposable copy in Chrome (desktop and phone width): status line, library cards, filters, Releases dialog, Ignore, Downloads table, Settings save and invalid-folder message, job buttons; no page errors (TMDb posters cannot load in the build sandbox).
- Not tested against live indexers, SABnzbd, BitTorrent or Plex: confirm the first downloads on the server.
