## v18.3.3 — Library Locations and Processing Review

- Manage library roots: add, edit unused paths, set default, remove unused paths.
- Block removal/replacement when shows use a path; list affected shows for reassignment.
- Add Show and Edit Library Folder use configured roots and preview destinations.
- Edit show destinations, optionally updating stored episode paths for files already moved.
- Direct Library editor, reviewed-file approval controls, and unmatched/blocked explanations.
- Free/total disk space with background checks and unavailable status.
- Compact database sizes in KB/MB/GB.
- Restart TV Manager to activate backend changes, then refresh the browser.

Configuration changes do not move or delete media files. Reassign shows before replacing a root they use. Source releases now include a version bump, notes, GitHub push and version tag per iteration.

### Validation and activation

- Focused location-management, destination editing, disk-space and processing-review checks passed.
- Python compilation and all JavaScript syntax checks passed.
- Full pytest: **244 passed, 8 failed**. Outstanding failures: magnet hash helper (1), scheduler lease behavior (2), Windows database/import temporary-file cleanup (5). This is not a fully green release.
- The running server requires a restart; an earlier restart attempt was blocked by Windows process permissions.
