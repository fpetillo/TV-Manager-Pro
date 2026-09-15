# TV Manager project review — 15 September 2026

## Assessment

TV Manager has substantial local coverage, but full SickChill parity is not achieved. The updated inventory contains 32 feature families: 12 locally complete, 19 partial, and one missing. These are coverage categories, not a percentage of product quality. A working configuration screen does not establish working integration with every external service.

This review covered the source/module inventory, routing/navigation, show and season displays, settings, acquisition, scheduled work, post-processing/media updates, database protection, existing regression coverage, and the upstream feature/adapter inventory. It is not a line-by-line security audit or certification that every possible runtime condition was exercised.

## Problems corrected in v18.6.0

| Problem found | Resulting behavior |
|---|---|
| Show Detail requested count-free responses, then rendered zero totals and undefined season counts | Header counts use the counted response after the header renders; season choices use the season summary and preserve zero considered episodes |
| Bulk searches had no safe stop | Active Jobs offers Stop Search; a running search finishes its current episode, leaves remaining episodes untouched and reports Cancelled with progress |
| Concurrent searches/handoffs could overlap on an episode | Per-episode OS locks coordinate search and handoff; active download records are rechecked inside the handoff lock |
| Simulation mode could be bypassed by individual automatic grabs | The shared episode search enforces simulation mode for automatic handoff; explicit manual release submission remains separate |
| Imported dates were compared as raw strings in search paths | Search eligibility, Missing and Upcoming normalize imported dates; future and unrecognized dates do not enter automatic missing searches |
| An old Completed download record could prevent replacement of a now-missing file | Show bulk eligibility excludes active handoffs but permits a missing, wanted episode with completed history to be searched again |
| Provider failures and refused media refreshes could look successful | Episode, bulk and recent/backlog job errors are exposed; explicit failed/error results update scheduler history as Error; unsuccessful Plex refresh requests become failed jobs |
| Recent/backlog progress called len() on an integer | Progress uses the searched count returned by the engine |
| One failing provider could hide available results | Show Detail displays a provider warning alongside results from working providers |
| The configurable worker limit was unused by the central job runner | API background job execution respects the configured limit (1–16); excess work waits |
| Arming automation enabled every scheduler row | The master switch preserves the Enabled choices for individual jobs; Settings explains this behavior |
| Case-insensitive settings edits could create shadow values | Edits retain the stored canonical section/name instead of inserting a differently cased key |
| Empty/missing databases were reported healthy, and rapid backups could collide | Checks reject empty/missing files; snapshots use unique names, sanitized reasons, and an atomically replaced manifest protected against concurrent in-process updates |
| A backup test wrote fixtures into the application's backup directory | The test redirects all backup paths to its temporary directory |

## Verification

- 318 automated tests passed in the final release run. New coverage exercises lock contention, repeated handoff, simulation, queue limits, queued/running cancellation, imported dates, completed-history replacement, setting preservation, reported service errors, counted Show Detail responses and retained partial search results.
- All 47 top-level Python modules parse, and all 38 application JavaScript files pass syntax checks.
- Dependency consistency check passed; this is not a vulnerability scan.
- An isolated Flask route sweep returned HTTP 200 for 41 static HTML page routes (including aliases). Literal template links resolved to registered routes. Dynamic navigation and every integration action were not exhaustively exercised.
- Browser verification used an isolated source copy and synthetic database on port 5051. A 35-episode search stopped after six episodes, displayed Cancelled and 6/35 processed, and left 29 unsearched. No downloads were submitted.
- Browser arming/pausing retained one enabled job and ten disabled jobs. Show Detail displayed 35 considered / 0 ignored / 35 total, Season 1 (35), and collapsed 0/35 downloaded. A simulated failed provider warning appeared alongside a result from a working test provider.
- Production was read only during review; it reported v18.5.14 and no active jobs in the recent-job snapshot. Media, credentials and production settings were not used as test fixtures.

## Remaining priorities and acceptance criteria

| Priority | Gap | Evidence / acceptance needed |
|---|---|---|
| High | Native restore and restart recovery | Database Safety has backup checks and guidance, but no complete native restore transaction. Add isolated restore preview, schema/config validation, rollback, and recovery drills before claiming restore parity. |
| High | Durable jobs and uncertain downloader outcomes | Manual jobs are in memory; scheduler/activity history is separate. Persist jobs, reconcile after restart, bound pending queues, and handle a downloader accepting a request before a timeout or DB-write failure. Per-episode locks alone do not guarantee exactly-once external delivery or season-pack deduplication. |
| High | End-to-end configured service acceptance | Verify search → selection → submission → completion/failure → processing → media scan for every supported configured client. This review used synthetic responses, not live service credentials. |
| High | Archive processing and script hooks | No full archive extraction/extra-script workflow exists. Require traversal/symlink protection, collision handling, resource limits, explicit executable configuration, timeout/cancellation and failed-job reporting. Downloader-side extraction is currently an operational alternative, not built-in parity. |
| Medium | Provider and downloader roster | Generic Newznab/Torznab does not reproduce site-specific cookies/login/scraping. Some upstream clients are missing. Blackhole currently produces .url descriptors, not native NZB/torrent payloads, so ordinary watch-folder compatibility is incomplete. |
| Medium | Indexers, numbering and anime | Native TVDB/TMDb exist; AniDB and existing-library provider/DVD-order migration remain missing. Complete XEM multi-mapping, aliases/group coverage and live acceptance remain open. |
| Medium | Subtitle and notifier coverage | OpenSubtitles and six native notification services cover part of the upstream roster. Verify service-specific behavior and add relevant maintained adapters with acceptance fixtures. |
| Medium | Calendar/feed | Upcoming is an air-date list. Calendar grid and iCalendar subscriptions are absent. |
| Medium | Configuration completeness | Editable imported settings can lack a corresponding native behavior. Add typed validation and explicit support indicators; check startup-only options and dedicated editors. |
| Medium | Performance and accessibility | Run large-library/network-failure load tests, keyboard/mobile checks across every page, pagination/concurrency tests and contrast/focus review. The browser checks here covered changed workflows, not all devices. |
| Medium | Metadata, packaging and operational security | Finish NFO/artwork consumer compatibility, clean-install/upgrade/restore drills, dependency vulnerability review, authentication/proxy/TLS deployment testing, and platform-specific service acceptance. |

Scheduler work still uses its separate per-job leases rather than the API worker pool. The backup manifest lock coordinates threads in one process, not competing application processes. Job cancellation is intentionally available only for bulk show searches with a safe stopping boundary. A successful Plex scan request means Plex accepted the request; it does not prove indexing finished.

## Sources and maintenance

Comparison references: [SickChill official features](https://sickchill.github.io/), [upstream source](https://github.com/SickChill/sickchill), [configuration settings](https://github.com/SickChill/sickchill/wiki/Settings-explained), and [remaining settings](https://github.com/SickChill/sickchill/wiki/Remaining-settings-explained). Upstream master was verified at `e1f8475ded8dd77662fad3ba9488740133ca8ce1` on the review date. An upstream adapter's presence does not prove that its service still operates.

The [parity matrix](SICKCHILL_PARITY_AUDIT.md) and in-app catalog carry the same 32 coverage rows. Re-evaluate each row against implementation and service evidence when delivering subsequent releases; do not mark parity complete merely because settings or adapter names exist.

## Activation

v18.6.0 is a source release. Restart TV Manager normally and refresh open pages to activate all backend changes. This review does not restart the existing production process.
