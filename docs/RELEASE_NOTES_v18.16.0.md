# TV Manager v18.16.0 — Delete download folders after moving

Built on v18.15.0.

## What changed

Post Processing has a new setting, **Delete the download folder after its episodes are moved**, under Source folder next to the archive option. It is off by default; tick it and press **Save Processing Settings**.

When it is on and the processing method is **Move**, after each run (manual or automatic):

- Each release folder inside the completed-downloads folder whose videos were all moved is deleted, together with anything left in it: .nfo, .txt, images, sample videos and so on. Associated files that TV Manager moves with the episode are moved first, as before.
- A folder that still holds a video that was not processed is kept, so an episode is never lost. This happens, for example, when only some episodes of a pack were selected.
- The completed-downloads folder itself is never deleted, and files sitting directly in it are not affected.
- Files extracted from archives are not covered; their original archive folder is left in place.
- Copy, Hardlink and the symbolic-link methods never delete anything, because they rely on the source staying in place.

After processing, the page lists the folders removed (with the number of leftover files deleted) and any folders kept with the reason. The event log records `download_folder_removed`, `download_folder_kept` and `download_folder_remove_error`. If a folder cannot be removed, for example because another program has a file open, the episodes are still imported and the run reports the folder as an error.

The setting is `General / delete_source_folder` (default `0`) and is returned and accepted by `/api/postprocess/config`.

## Validation

- 550 passed, 11 skipped (Windows-only PowerShell, updater lease and service checks on the Linux build host).
- New tests run a real TV Manager copy with three cases in one run: a finished release folder with leftovers and a Sample subfolder is removed; a pack folder with an unselected episode is kept; a file directly in the downloads folder is imported and the downloads folder survives. Also: setting off removes nothing; Copy removes nothing.
- Browser check on a disposable copy: the checkbox saves and reloads, processing moved the episode, the folder was removed and listed on the page, no page errors.
