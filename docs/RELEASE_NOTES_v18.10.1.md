# TV Manager v18.10.1 — Search names with punctuation and accents

TV Manager now tries alternate spellings automatically when an episode search returns no acceptable release under the saved show name. You can keep the proper title in your library.

For **Wonka's The Golden Ticket**, searches can try **Wonkas The Golden Ticket**, **Wonka s The Golden Ticket**, and **Wonka The Golden Ticket**. Similar normalization covers curly apostrophes, hyphens/dashes, periods, punctuation, ampersands/and and common accented letters. For example, Spider-Man can search as Spider Man or SpiderMan, S.W.A.T. as SWAT, and Café as Cafe.

## Where it applies

- Individual episode searches from Show Detail and classic Shows.
- Automatic recent/backlog searches and Find & Download Missing Episodes, through their shared search engine.
- Season-pack searches, including saved show aliases and scene exceptions.
- Imported Newznab and custom Newznab/Torznab providers, including providers that require a plain text search with episode numbering.

No settings switch or show rename is required. Successful alternate episode results display **Matched using:** and the spelling used. The stored display name, name override, metadata IDs, folders and episode numbering remain unchanged. Titles you previously renamed stay as you saved them; this update does not guess their original names.

## Matching and provider limits

The original spelling is searched first. If it produces no acceptable release, TV Manager tries up to six distinct spellings total per title/alias and numbering variant, stopping that sequence once it finds acceptable results. Normal titles and successful original searches do not generate extra spelling requests. Results are deduplicated, existing quality/resolution and seed requirements still apply, and provider errors/rate limits stop retries for that provider while retaining earlier results.

Broader episode results must match the complete normalized title prefix and requested episode, scene number, airdate or anime absolute number. Accept rules cannot turn a rejected broad title match into an automatic download. Season packs must match the show and season and exclude individual episode releases. Years/country markers are retained to distinguish similarly named shows. This handles spelling differences caused by punctuation/spacing/accents; it does not automatically download arbitrary approximate or misspelled show titles. Use a saved alias/scene exception for a genuinely different release title.

This changes release searches against configured download providers. Add-show metadata discovery and local list filters are unchanged. Availability still depends on what the indexer has indexed and its own query behavior.

## Validation and update

- 461 tests passed; two existing Windows symbolic-link permission checks skipped.
- All 68 top-level Python modules and 41 JavaScript assets pass syntax checks; dependency consistency passes.
- New regressions cover spelling variants, bounded requests, original success without retries, unchanged saved names, automatic acquisition selection, wrong shows/episodes/reboots, quality rejection, rate limits, partial results, aliases, packs, and real XML transport with capability caching/text fallback.
- Browser QA in a separate synthetic installation verified both show screens: the original Wonka title found a release using the third query, Wonka s The Golden Ticket, with the successful spelling displayed. No console errors, real indexer requests, live downloads or production changes.

Source: https://github.com/fpetillo/TV-Manager-Pro/tree/v18.10.1

ZIP: https://github.com/fpetillo/TV-Manager-Pro/archive/refs/tags/v18.10.1.zip

Stop TV Manager and back up the existing installation. Extract the tagged ZIP separately, then merge the contents of TV-Manager-Pro-18.10.1 into the installation, replacing source files while retaining the database, settings, .env, runtime history and the server's working .venv. Follow the [existing-installation update procedure](RELEASE_NOTES_v18.10.0.md#update-an-existing-source-installation), using this release's ZIP/version. Restart normally and press Ctrl+F5 in open pages. No new executable or installer was built, and 192.168.1.16 was not updated or restarted by this work.
