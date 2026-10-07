# TV Manager v18.13.0 — Show Queue scans, Post Processing shortcut, compact main pages, Trakt filters

Built on v18.12.0. Source release; no new Windows EXE or service package is included (see Activation).

## Show Queue: Scan Files

- Each Show Queue row has a **Scan** button (new **Files** column). It runs the existing *Scan Existing Files* job for that show, which records episode files already in the show folder, and then refreshes the season/episode counts in the queue.
- **Scan Files for Selected** scans every show ticked with the queue checkboxes (or *Select Visible*) in one background job. The selection is the same one used by *Set Resolution* and is kept across pages and filters.
- Progress shows on the page and in Active Jobs. Shows without a library folder or with an unreachable folder are listed as not scanned; the remaining shows still complete. A bulk scan accepts up to 500 shows and can be stopped from Active Jobs between shows.
- New endpoint: `POST /api/shows/scan-library/start` with `{"show_ids":[…]}`. The single-show endpoints are unchanged.

## Post Processing at the top of every page

A **Post Processing** button now sits beside *Search TV Manager* at the top-right of every page. On phones it is pinned at the top beside the Menu button. The script-free support pages (About, Routes) carry a plain Post Processing link in their menu.

## Compact main page

Launchpad's top cards are smaller: compact header and logo, a single-line readiness banner with a smaller score, and the installation checks laid out as a grid of small cards instead of full-width rows. Package checks, statistic tiles and recommended actions are tighter. The page is about 40% shorter on a 1440×900 screen (4,065 → 2,363 px with a small test library). Dashboard uses the same compact header, banner and statistic tiles. Content and links are unchanged.

## Trakt Discover filters

- **Hide shows already in my library** removes results that match a library show by Trakt, IMDb, TMDb or TVDB ID, or by exact title plus first-air year. When hiding, TV Manager reads up to six Trakt pages to fill the requested count and reports how many library shows were hidden.
- **First aired from / to** limits results to a year or a range (for example 2020–2024) using Trakt's own year filter, for both the category lists and name search.
- **Load More** continues from where the last load stopped. The toggle and years are remembered in this browser; **Clear filters** resets them.

## Other

- A brand-new database no longer fails background jobs before its settings table exists; the worker limit falls back to its default of 4.

## Validation

- pytest: 524 passed, 11 skipped. The skips are Windows-only PowerShell, updater-lease and service checks that cannot run on the Linux build host. New tests cover bulk scan updates, input validation and partial failures, the unchanged single-show scan, Trakt year ranges, library matching, page fill-up and bad-year handling, the shortcut on every navigated page, and the compact-page styles.
- 72 Python modules parse, 43 JavaScript files pass `node --check`, and RELEASE_MANIFEST.json is valid JSON.
- `tests/verify_postprocess_ui.cjs` fails with `document.createElement is not a function` on both this release and unmodified v18.12.0; Post Processing code was not changed. This is a pre-existing issue in that standalone script.
- Browser QA used a disposable copy with synthetic shows and files. Row scan: 0/8 → 3/8 downloaded. Selected scan of two shows: one file matched, counts refreshed. The empty-selection prompt was shown. The shortcut appeared on Show Queue, Jobs, Help, Trakt and Post Processing (marked current), navigated correctly, and sat at the top on a 390 px phone width. Launchpad and Dashboard were checked at desktop and phone widths. Trakt controls, remembered choices, the out-of-order year message and the request parameters were checked. No Trakt credentials were available, so live Trakt results were not loaded; the filtering logic is covered by tests.
- Windows PowerShell scripts were not executed on this release; only the default version strings changed.

## Activation

Update the server source with `update-server.ps1` (defaults to 18.13.0), restart TV Manager, confirm 18.13.0 in About and press Ctrl+F5. The v18.12.0 service ZIP does not contain these changes; rebuild the service package on Windows with `installer/windows/build-service-package.ps1` before installing as a service. No production server was updated.
