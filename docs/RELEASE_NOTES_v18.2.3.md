# TV Manager v18.2.3 — Fast Show Open & Subtitle Scan Guard

This hotfix targets the two workflows that could still feel hung on large or network-backed libraries.

## Show loading

- Show Detail opens the core show record first using a fast endpoint.
- Episode rows are loaded with quick paging instead of waiting on a full count query.
- Expensive episode totals are refreshed after the page is usable.
- Episode row queries select only the fields needed by the UI.
- Slow count queries no longer block the first usable screen.

## Subtitle scans

- Subtitle scans are capped by `TVManager / subtitle_scan_max_candidates`, default `200`.
- UNC and mapped network paths are skipped by default to avoid blocking on unavailable NAS/SMB paths.
- Set `TVManager / subtitle_scan_network_paths = 1` to include network paths.
- Skipped network items are marked `SkippedRemote` instead of freezing the scan.

## New/updated settings

```text
TVManager / subtitle_scan_max_candidates = 200
TVManager / subtitle_scan_network_paths = 0
```

## Database performance

Added episode indexes for show-detail paging, status filtering, ignored-rule filtering, and title lookup.
