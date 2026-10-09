# TV Manager v18.17.0 — Scan Show Folder on the show page

Built on v18.16.0.

## What changed

The show page (opened by clicking a show name in the Show Queue) has a **Scan Show Folder** button next to Refresh, above the episode list. It scans that show's library folder in the background and then reloads the page, keeping the season and status filters you were using, so a Wanted (missing) view updates in place.

A show folder scan now refreshes in both directions:

- Episode files found in the folder are recorded and marked Downloaded, as before.
- Episodes whose recorded file no longer exists are marked missing again: the path is cleared and Downloaded becomes Wanted. The result lists them (for example "Missing again: S01E01") and the event log records `library_scan_missing`.
- This only happens after the show folder itself is confirmed reachable. If the folder or its share is offline, the scan stops with an error and changes nothing.
- Files in the folder that could not be matched to an episode are listed under the result.

The same refresh applies to the Scan button on each Show Queue row and to Scan Files for Selected.

## Validation

- 553 passed, 11 skipped (Windows-only PowerShell, updater lease and service checks on the Linux build host).
- New tests run a real TV Manager copy through the page and API: a file on disk is recorded, a recorded file that was deleted becomes Wanted with its path cleared, and an unreachable show folder fails the scan without changing any episode.
- Browser check on a disposable copy: Show Queue → show page → Wanted filter → Scan Show Folder; result shown, episodes updated, no page errors.
