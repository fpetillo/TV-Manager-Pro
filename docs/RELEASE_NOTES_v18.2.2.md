# TV Manager v18.2.2 — Fast Loading Hotfix

This hotfix addresses slow/hanging screens during subtitle scans and show loading.

## Fixes

- Subtitle scans no longer hold one long SQLite write transaction.
- Subtitle scans now perform file checks without holding the database writer lock.
- Subtitle status updates are written in small batches.
- Subtitle scans pause after a configurable safety window so network shares cannot freeze the UI.
- Show Detail read APIs now use read-only database connections that do not wait behind local writer jobs.
- Show loading now times out with an actionable message instead of appearing frozen.

## New setting

`TVManager / subtitle_scan_max_seconds` defaults to `30`. Increase it if the library is local and fast; lower it if scans run against slow NAS/network shares.
