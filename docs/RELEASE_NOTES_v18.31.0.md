# TV Manager v18.31.0 — Movie destination folders and Plex folder translations

Built on v18.30.0.

## Why

The Plex servers name their movie folders their own way (for example `/data/movies` or `M:\Movies`), and the names differ from server to server and from what the TV Manager server reaches (`\\192.168.1.222\Media_5\Movies`). v18.30.0 tried to infer the destination from Plex's library paths. That cannot work reliably, so where movies go is now configured on the TV Manager server and Plex's paths are used only to tell each server what to scan.

## What changed

- **Movie destination folders.** Movies › Settings › *Where new movies go* takes one or more folders written the way this server reaches them. Each folder shows whether it is reachable and its free space.
- **Choosing a folder.** *Most free space* (default) or *In the order listed*, keeping a free-space reserve per drive (default 50 GB). An upgrade replaces the old copy in the folder it already lives in. If every drive is below the reserve, the movie goes to the drive with the most room as long as it fits.
- **Tell Plex about new movies.** For each Plex server, optional translations: *folder on this server → same folder as that Plex server sees it*. After each import TV Manager asks every enabled Plex server to scan:
  - with a translation: just the new movie's folder, in that server's own path;
  - without one (or if the translated path is not in a movie library there): all of that server's **movie** libraries (never TV).
  Each server's movie folders, read during the library scan, are listed as suggestions.
- **Activity log.** Each import names the destination and what each server scanned ("Plex Den: scanned /data/media5/movies/Dune (2024)"; "Plex Office: scanned all movie libraries (no folder translation set)"). Only a failed scan request is a warning.
- **Moving earlier imports.** Movies imported outside the destination folders are listed under *Where new movies go* with **Move N movies into the destination folders**; each server is told about each moved movie.
- The v18.30.0 red "not in a Plex movie library" check is removed: it judged folders by Plex's paths, which this release stops relying on.
- Older installs: the previous single movie library folder becomes the first destination folder.

## After updating

1. Movies › Settings › *Where new movies go*: enter the movie folder(s) as this server reaches them, then Save.
2. *Tell Plex about new movies*: for each Plex server whose folder names differ, tap **Add translation** and fill both sides. Skipping this still works; that server scans all its movie libraries.
3. Use **Move N movies into the destination folders** if earlier imports landed elsewhere.

## Validation

- 5 new tests: destination folders validated and kept in step with the older setting; most-free / in-order / reserve / upgrade-stays-put / no-room choice; per-server path translation (UNC to Linux path, UNC to drive letter, longest match, no match); Plex told in its own path for one server and all movie libraries (not TV) for another; import picks the folder with room and the scan note names each server's result.
- v18.30.0 tests updated for the removed Plex-path check.
- Chrome on a disposable copy, desktop and phone width: destination list with free space, per-server translation editor, add and save a translation.
