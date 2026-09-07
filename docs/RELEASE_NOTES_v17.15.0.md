# TV Manager v17.15.0 — Background Jobs, Scheduler, Metadata Art Polish

This release moves TV Manager closer to a professional SickChill replacement by adding background-job workflow, broader scheduled maintenance, and richer metadata/art support.

## Added

- New Active Jobs screen at `/jobs`.
- Background job endpoints for episode search, recent/backlog search, show metadata refresh, post-processing, missing metadata, and artwork refresh.
- Scheduler jobs for missing metadata, artwork refresh, Library Health scan, and database protection.
- Settings Automation updates for the new scheduled jobs.
- Missing metadata refresh workflow for shows missing IDs, overview, poster, episode titles, dates, or artwork.
- Episode artwork metadata fields: `still_url`, `still_path`, `tmdb_episode_id`, `metadata_updated_at`.
- Library Health buttons for missing metadata and show/episode artwork refresh with progress bars.
- Post-processing progress job mode.

## Improved

- Long-running operations can continue after switching screens.
- Show detail episode search now runs as a background job and displays a progress bar.
- Manual scheduler runs now return a job and can be monitored through the Active Jobs screen.
- Database/config protection remains part of professional distribution readiness.

## Validation

- Python compile check
- JavaScript syntax check
- v17.15 background/scheduler tests
