# TV Manager v18.28.0 — Complete movie library list

Built on v18.27.0.

## What changed

The Movies library scan now builds a complete list of the movies you own from every drive and folder Plex knows about, so nothing you already have is downloaded again.

- **Every Plex server and movie library** is read page by page (1,000 at a time), so very large libraries are read in full. IMDb IDs from older Plex agents are matched as well as TMDb IDs.
- **Every folder behind those Plex libraries** that the server can reach is scanned too, plus the movie library folder and a new **Other movie folders** list (Movies › Settings, one per line) for movies Plex does not know about. Previously only the one movie library folder was scanned on disk.
- Folders recognized: `Title (Year)`, `Title [Year]`, release-style names with a year, loose video files, and one level of grouping folders (`A`, `B`… or genres). Hidden, trash and NAS system folders are skipped; nested folders are read once.
- **What the last library scan read** (Movies › Settings): every Plex server and library, every folder, the number of movies each gave and any problem, with the total owned.
- If a Plex server or library cannot be read, automatic adding of new movies is paused until a complete scan, so movies you own there are not downloaded again. A movie TMDb adds is also matched to an owned copy by IMDb ID.

Details: [MOVIES.md](MOVIES.md).

## Updating to 18.28.0

Download `update-server.ps1` from the v18.28.0 tag and run it, as in [WINDOWS_SERVER_UPDATE.md](WINDOWS_SERVER_UPDATE.md); start TV Manager with run.ps1. Then Movies › Settings › **Scan library now**, wait a minute, refresh, and check **What the last library scan read**.

## Validation

- 5 new tests: two Plex servers and three libraries read page by page with TMDb, IMDb and legacy-agent IDs; an unreachable Plex server reported and discovery paused; import folder, other folders, Plex folders, letter and genre grouping, loose files, trash skipped, nested folder read once, unreachable Plex folder covered by Plex vs unreachable listed folder reported; owned-by-IMDb match; folder list validation.
- Chrome on a disposable copy: the scan table and the Other movie folders box render with no page errors.
