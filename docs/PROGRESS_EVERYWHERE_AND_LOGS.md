# Progress Everywhere and Professional Logs

TV Manager v17.18.0 continues the SickChill parity polish pass by moving additional long-running operations into background job mode with visible progress.

## New progress-backed operations

The following operations now have job-backed progress indicators and can continue while the operator changes screens:

- Subtitle audit scan
- Subtitle job runner
- Post Processing folder preview scan
- Post Processing apply/process run
- Episode search
- Downloader handoff from a selected search result
- Existing background metadata, artwork, library health, database protection, import, and search jobs

## Active Jobs

Open `/jobs` to see running and recent work. Job records expose percent, stage, message, processed count, total count, succeeded, failed, current show/file, recent errors, and result payloads.

## Subtitle audit

Open `/subtitles` and click **Scan Library**. The page now starts `/api/subtitles/scan/start`, polls `/api/jobs/<job_id>`, and renders progress instead of waiting silently.

## Post Processing preview scan

Open `/postprocess` and click **Preview Folder**. The page now starts `/api/postprocess/scan/start`, tracks folder walking and episode matching, then renders the preview result.

## Downloader handoff monitoring

From a show detail episode search result, **Send to Downloader** now starts `/api/search-results/<id>/grab/start`. The button displays progress and the job appears in Active Jobs.

## Logs & Events

Open `/logs` for a filterable, sortable operational log view. Filter by level, event type, and search text; sort by date, level, event, show, message, or ID. The log viewer is designed to help operators troubleshoot provider errors, downloader handoff, scheduler runs, library scans, and post-processing decisions.
