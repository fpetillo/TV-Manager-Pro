# TV Manager v18.30.0 — Movies land where Plex looks

Built on v18.29.0.

## What changed

Movies were downloading and importing, but into a folder that no Plex movie library watches, so Plex never showed them. When the movie library folder was not set by hand and the Plex movie folders were not reachable from the server, TV Manager fell back to a "Movies" folder next to the TV folder.

- **No more guessing.** The movie library folder is detected only from Plex movie library folders. If Plex has movie libraries but none is reachable from the server, nothing is guessed: Movies asks you to choose, and searching waits until you do. (The folder next to TV is still used when there is no Plex server at all.)
- **Plex check.** Movies › Settings now says whether the movie library folder is inside a Plex movie library: green when Plex will show new movies, red when it will not. A red check also shows on the Movies status line, the dashboard Movies card and the Launchpad.
- **One-tap choice.** Your Plex movie folders are listed under the folder box; tap one to use it. A folder the server cannot reach is shown as Plex names it, with a pointer to Path Mappings.
- **Move misplaced movies.** Movies that TV Manager imported outside the movie library folder are listed with **Move N movies into the library folder**. Each movie folder is moved, its record updated, and Plex scans the library. Movies already in the library folder are never overwritten; movies found in Plex are never touched.
- **Every import records the Plex result.** The activity entry says where the file went and what Plex was asked to scan ("Plex — Den: scanned the movie folder"), and is a warning when the folder is outside Plex. The Downloads tab note shows the full destination.
- **BitTorrent fix.** For a single-file torrent, BitTorrent/uTorrent reports the folder it was saved in. TV Manager now adds the torrent name (as Sonarr does), and never treats a whole download folder as one movie, so the wrong file cannot be imported.

## After updating

1. Open Movies › Settings and tap **Scan library now**; wait a minute and refresh.
2. If the Plex check is red, tap one of your Plex movie folders (or type the right folder and Save).
3. Tap **Move N movies into the library folder** to bring the earlier imports into Plex.

## Validation

- 7 new tests: uTorrent single-file save folder, download folder never imported as one movie, Plex check (inside, outside, no Plex), no guessed folder when Plex folders are unreachable, import note and Plex scan result, warning when outside Plex, and moving imported movies (skip existing, leave Plex movies alone, update records, scan Plex).
- Chrome on a disposable copy: red Plex check, one-tap Plex folder, green check, move list and button.
