# Post Processing Workflow

TV Manager post processing is designed to feel familiar to SickChill operators while adding safer preview/apply controls.

## Recommended operator flow

1. Open **Post Processing**.
2. Confirm the configured **Completed TV downloads** folder.
3. Optionally enter an **Override folder** for a one-time run.
4. Click **Preview Folder**.
5. Review matched files, destination paths, blocked upgrades, and unmatched files.
6. Select only the files you want to process or choose **Process All Approved**.
7. TV Manager applies naming, move/copy/hardlink behavior, associated-file handling, upgrade protection, and audit history.

## Folder selection

Web browsers cannot safely browse the server filesystem the same way a desktop app can. The operator enters the folder path as seen by the TV Manager server:

- Windows example: `D:\Downloads\TV`
- Linux example: `/downloads/tv`
- Docker example: `/downloads/tv`, mapped from the host volume

## Safety rules

- Preview does not move files.
- Blocked upgrades are not processed.
- Existing destination files are not silently overwritten.
- Existing library files are staged through managed replacement safeguards before replacement.
- Operators can use **Process Selected** for chosen preview rows instead of processing the entire folder.

## SickChill replacement guidance

Set the configured folder to the same completed TV download directory that SickChill used. Run preview first after migration and confirm naming/path output before enabling automatic workflows.

## Add Show destination selection

Search and Trakt Add Show now open a library-folder picker using General / root_dirs, including the imported default root index. Review the root, show folder name and full destination before confirming Add Show. Both add routes save location and enable season subfolders; a destination is required. Invalid folder names and unconfigured roots are rejected. The destination folder is created by post-processing when needed.

For existing shows missing a location (such as Breaking Bad and Friends), open Show Detail and choose Set Library Folder. Saving a missing destination does not move any existing files. This action does not relocate shows already configured with a destination.

Restart TV Manager to load the new endpoints, then refresh the browser. Checks: tests/verify_library_destinations.py covers both add routes, missing-location repair, root defaults, path validation and supported path styles.

### Editing an existing show folder

Open Show Queue, click the show name, then select **Edit Library Folder** on Show Detail. The Library show panel also links to this editor. It is available for shows with and without a configured path.

Saving sets the destination for future post-processing and preserves season-folder preferences. To correct database paths after files have already been moved, select **Update stored episode paths too**. Only paths under the old show folder are rebased; other paths remain untouched. This does not move files or verify that they exist at the new location. Stale edits are rejected if another session changes the folder.

### Library disk space

Library Storage in the navigation shows free space, total capacity, percentage used and check time for each configured TV root. Add Show and Edit Library Folder display free space beside root choices and detailed readings within the picker. Paths sharing a disk may show the same available capacity; readings are not summed. Values use MB/GB/TB.

Disk checks run in a bounded background worker pool, with one check in flight per path and a 60-second cache. Slow and unreachable storage are labeled rather than reported as zero free space. The page refreshes pending readings for up to 30 seconds; Refresh Space checks again, using cached results until expiry. Restart the server for /api/library/storage and /library-storage to become available.

The classic Library panel now opens Edit Library Folder directly as a dialog; it no longer redirects to Show Detail. Verified by opening the picker for Breaking Bad in the running browser and cancelling without saving.
