# TV Manager v18.23.0 — Speed

Built on v18.22.0.

## Why it was slow

Measured on a synthetic library at the server's scale: 1,200 shows, 114,000 episodes (71,000 with files), 400,000 log rows and a 270 MB database. Every page and API that opens without parameters (135 routes) was timed. The causes, largest first:

1. **The menu's Safety badge re-read the whole database, and every backup, every 30 seconds in every open tab.** Each refresh ran a full integrity check of the live database and of every backup copy, and computed a SHA-256 of each backup. With 25 backups of a 200 MB database that is several GB of disk reads per tab every 30 seconds, competing with everything else on the server.
2. **Launchpad, Dashboard, Workflow and Setup checked every episode file on the media share on every load:** 71,000 separate network file checks per page view.
3. **Page views waited for background jobs.** Every database connection took TV Manager's single writer lock when it opened, even to read one setting. While a scan, import or other job was writing, pages stalled until it finished.
4. **The Operations page and library conflict check opened a new database connection for each episode** (72,000 connections): 54 seconds each.
5. **The log viewer and the error badge scanned the whole log table**, which was never trimmed and had no index on the level.
6. **Show Queue, Upcoming, Missing and searches ran a Python date conversion for every episode row**, and the Show Queue ran seven separate sub-queries per show.

## What changed

| Area | Change |
|---|---|
| Menu badges | One request (`/api/nav/badges`) instead of three. Skipped while the tab is hidden. |
| Database integrity check | Reused for 15 minutes and refreshed in the background; never blocks a page. Unchanged backup files are checked once, not on every refresh. The System page uses the same cached check. |
| Library health on summary pages | Built once and reused for 10 minutes (rebuilt in the background). Files are checked by listing each season folder once, 16 folders at a time: 9,000 folder listings instead of 71,000 file checks. The Library Health page still builds a fresh report each time, now with the faster check. |
| Writer lock | A connection takes the writer lock at its first write, not when it opens. Reads never wait for background writers; writes still queue one at a time. Set the environment variable `TVMANAGER_EAGER_WRITE_LOCK=1` to restore the old behaviour if ever needed. Settings and security checks use read-only connections. |
| Operations / conflicts / root folders | One path-mapping lookup per run; show folders checked in parallel. |
| Logs | Indexes on level and event type; counts skip unnecessary joins. |
| Dates | ISO dates are handled inside SQLite; only legacy values (SickChill ordinals and the like) call Python. |
| Show Queue | One pass over the episodes for all shows. Output verified identical to 18.22.0 for eight sort and filter combinations. |
| Database settings | 32 MB page cache per connection, memory-mapped reads, in-memory temporary sorting. New indexes on logs, downloads, episode status and air date; statistics refreshed after they are created and by the nightly database job. |
| Network | Pages and API responses are gzip-compressed (the Missing list goes from 714 KB to 32 KB). CSS and JavaScript are cached by the browser until the next release. |
| Log retention | The nightly database protection job deletes log rows older than: activity log 180 days, API access log 30 days, scheduler run history 90 days. Change with the settings `TVManager` / `activity_log_retention_days`, `api_access_log_retention_days`, `scheduler_runs_retention_days`; `0` keeps everything. |
| Automation intervals | An interval set for a job in **Settings → Automation** is now kept across restarts. Before, every restart reset Recent search, Backlog search and the other jobs to their defaults (Backlog: every 2 days). |

## Measurements

Synthetic library above, Flask test client, median of 3 requests, Linux build host (local disk, so network-share effects are not included and the gains on the server's media share should be larger):

| Request | 18.22.0 | 18.23.0 |
|---|---:|---:|
| Operations summary | 53,931 ms | 393 ms |
| Library conflicts | 51,868 ms | 320 ms |
| Safety status (badge, every 30 s per tab) | 1,231 ms | 3 ms |
| Logs / error badge | 1,174 ms | 7 ms |
| Library root health | 1,131 ms | 74 ms |
| Dashboard (full) | 992 ms | 66 ms |
| Workflow summary | 955 ms | 126 ms |
| Launchpad summary | 892 ms | 19 ms |
| Setup summary | 872 ms | 17 ms |
| Show Queue | 783 ms | 271 ms |
| System health | 256 ms | ~15 ms |
| Upcoming | 155 ms | 74 ms |
| All 135 routes together | 117.8 s | 12.8 s |

Requests over 500 ms: 13 before, 1 after (Safety status on its first call after a restart, while it checks the backups once).

**While a background job holds the database for 4 seconds:** Launchpad 3,804 ms → 3 ms, Settings sections 3,822 ms (when it was first in line) → 23 ms, Show Queue 795 ms → 245 ms.

**On the media share:** the summary pages made 71,066 file checks per view. They now reuse one report, rebuilt at most every 10 minutes with 8,979 folder listings, 16 at a time.

## Updating to 18.23.0

Download `update-server.ps1` from the v18.23.0 tag and run it, as in [WINDOWS_SERVER_UPDATE.md](WINDOWS_SERVER_UPDATE.md). The first start creates the new indexes (a few seconds on a 200 MB database). Press **Ctrl+F5** once in each browser.

The first nightly database job after the update trims logs older than the retention periods above. If you want to keep all history, set those settings to `0` before then.

## Validation

- 611 passed, 11 skipped on the Linux build host (Windows-only checks skipped); the suite also runs on GitHub's Windows runner.
- 8 new tests:
  - statement classification for the writer lock;
  - reads do not wait for a writer while a second writer does;
  - 6 threads × 80 concurrent writes lose nothing and the lock is released;
  - the lock is released on error;
  - the SQL date fast path gives the same result as the Python conversion;
  - folder-listing file check (one listing per folder, case and missing folders);
  - an app-level scenario covering the new indexes, the badge endpoint, the case-insensitive log filter, cached integrity checks, one shared summary report, one path-mapping lookup per run, gzip and cache headers, log retention including `0`, and an Automation interval surviving a restart;
  - the menu uses a single badge request.
- 1 existing test updated: the menu badges now use `/api/nav/badges`.
- Not performed: timing on the Windows server and its media share.
