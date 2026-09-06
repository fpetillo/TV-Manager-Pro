# TV Manager 15.0 Release Notes

## SickChill-compatible naming

TV Manager now applies the imported naming pattern during post-processing instead of merely preserving it as a setting.

Supported tokens:
- `%SN` — show name
- `%S` / `%0S` — season, unpadded/padded
- `%E` / `%0E` — episode sequence, including multi-episode files
- `%EN` — episode name(s)

The imported pattern `Season %0S/%SN - S%0SE%0E - %EN` therefore produces paths such as:

`Season 01/My Show - S01E01E02 - Pilot + Second Episode.mkv`

Windows-reserved filenames and invalid characters are sanitized.

## Post-processing preview

Preview now shows the exact final library path, inferred quality, rename decision, blocked upgrade reason, and multi-episode coverage before processing starts.

Associated `.srt`, `.ass`, `.ssa`, `.vtt`, `.sub`, `.idx`, `.nfo`, and artwork files that share the media filename stem can follow the renamed episode when `move_associated_files` is enabled.

## Duplicate-content detection

TV Manager can fingerprint library media using file size plus SHA-256 over the first and last MiB. Operations exposes a Content Duplicates scan to find identical media stored at different paths without hashing every byte of very large files.

Fingerprint results are cached using path, size, and modification time.

## Scheduler crash recovery

Scheduler jobs now use SQLite-backed leases. This prevents the same automation job from running simultaneously in two TV Manager processes.

On startup:
- expired leases are removed;
- scheduler runs left in `Running` state by a previous crash/restart become `Abandoned`;
- the System page can display active leases.

## Windows production runner

The existing `run.ps1` remains available and unchanged for compatibility.

After `setup.ps1` installs dependencies, `run-prod.ps1` can run TV Manager through Waitress. `install-production-startup.ps1` creates a restart-enabled Windows Scheduled Task for the production runner. `status.ps1` checks the local `/api/health` endpoint.
