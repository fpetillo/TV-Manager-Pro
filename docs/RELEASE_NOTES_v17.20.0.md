# TV Manager v17.20.0 — SQLite Lock Guard + Media Server Maintenance

This release hardens the professional background-job architecture introduced in the prior releases.

## Fixed

- Prevents scheduler and metadata refresh threads from crashing with `sqlite3.OperationalError: database is locked`.
- Adds a process-wide SQLite writer guard and a longer SQLite busy timeout.
- Adds retry handling for scheduler finish updates and logging writes.
- Adds an emergency plain-text log fallback if SQLite logging is temporarily unavailable.

## Improved

- Media Servers now support full add, edit, delete, test, refresh and watched-sync operations from the Advanced screen.
- Media server test, refresh and watched-sync actions can run as Active Jobs with progress feedback.
- Provider, webhook, show group, tag and retention policy maintenance now includes edit/delete paths so configuration is not one-way.
- Downloader handoff jobs now record a clear failed job state if the configured download client rejects a request.

## Operator note

The reported lock trace came from concurrent scheduler/background threads writing metadata state, scheduler status and activity logs at the same time. TV Manager now serializes local writer connections so only one thread writes to SQLite at a time while other work continues in the background.
