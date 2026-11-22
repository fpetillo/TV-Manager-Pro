# TV Manager v18.25.0 — Trash on the media share, with Empty trash

Built on v18.24.0.

## What changed

TV Manager never deletes a video file straight away. It moves it to trash. Until now that trash was `managed_trash` on the server's own drive, nothing ever emptied it, and only upgrades could be put back. Because the library is on a network share, every "move" to trash copied the whole video across the network onto the server's C: drive.

**Trash now lives on the media share**, in a `.tvmanager-trash` folder at the top of each library folder. For example, a library folder `\\192.168.1.221\Media\TV` gets `\\192.168.1.221\Media\TV\.tvmanager-trash`. Moving a file there is a rename on the same share: instant, with nothing copied to the server. The folder gets `.plexignore`, `.ignore` and `.nomedia` marker files so Plex, Jellyfin/Emby and Kodi don't list the trashed videos. To use one fixed folder instead, set it on the Trash page.

**New Trash page** (menu → Administration → Trash):
- **Totals:** size and number of files, overall and for each kind: replaced by an upgrade, removed by an upgrade rollback, duplicate cleanup, retention policy.
- **Every file in trash,** with where it came from, the episode, why it was moved, its size and when.
- **Restore** any file to where it came from. Upgrades go back through the normal rollback, so the episode record follows. Files removed by a retention policy are re-attached to their episode.
- **Empty trash:** everything, only files older than a number of days, or the files you tick.
- **Empty automatically after N days** (0 = never, the default). The nightly database protection job does the emptying.
- **Old trash on the server's drive:** files left in `managed_trash` from earlier versions are counted, and **Empty old server trash** deletes them.

Emptying deletes files for good. An upgrade whose old file has been emptied can no longer be rolled back.

All four places that move files to trash (upgrades, upgrade rollback, duplicate cleanup and retention) now use the new trash and record each file. Files that are not inside any library folder still go to the old `managed_trash` folder.

## Updating to 18.25.0

Download `update-server.ps1` from the v18.25.0 tag and run it, as in [WINDOWS_SERVER_UPDATE.md](WINDOWS_SERVER_UPDATE.md), or use the release ZIP with `-ArchivePath`. Then press **Ctrl+F5** in each browser.

Trash goes to the share only for library folders listed in **Library Locations**. Check that your TV folders are listed there. Then open **Trash** and use **Empty old server trash** to free the space held on the server's drive.

## Validation

- 616 passed, 11 skipped on the Linux build host (Windows-only checks skipped); the suite also runs on GitHub's Windows runner.
- New end-to-end test on a temporary library folder:
  - an upgrade, a duplicate cleanup and a retention run each move their file into `.tvmanager-trash` inside the library folder, which gets the three ignore markers;
  - Trash totals per kind are correct;
  - restoring the upgrade rolls it back; restoring the retention file re-attaches it to its episode; restoring twice is refused;
  - Delete selected and Empty all delete the files and remove the empty folders;
  - old server trash is counted and emptied;
  - a fixed trash folder is used when set;
  - bad settings and requests are refused;
  - automatic emptying keeps recent files;
  - the page and the menu link work.
- Browser check in Chromium on a disposable copy: Trash page with share and old-server items; no page errors.
- Not performed: a run on your server's share.
