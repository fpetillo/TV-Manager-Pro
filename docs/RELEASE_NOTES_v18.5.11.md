## 18.5.11 — Find and download missing episodes

Open a show from Show Manager and choose **Find & Download Missing Episodes**. Confirm the eligible count to search all seasons and automatically send the best acceptable release for each episode to the configured downloader. Progress and errors appear in Active Jobs; the page can be closed during the search.

No scheduler per-run cap applies. Aired, monitored episodes without recorded files are included; ignored, unmonitored, downloaded, queued, unknown-airdate and future episodes are excluded. Show pause/search settings and the global Specials exclusion are respected. Repeated clicks reuse the active show job, and eligibility is checked again before each episode. Simulation mode searches without sending downloads. Provider failures do not stop remaining episodes. Release quality rules and the failed-release blacklist use the existing search pipeline.

Validation: 305 tests passed, including uncapped selection, exclusions, duplicate starts, simulation, error continuation, successful handoff and eligibility recheck. JavaScript syntax passed. Isolated browser verified button, count confirmation and completion using a mocked provider; no real downloads sent.

Restart TV Manager and refresh the show page. Download handoff is not download completion; unmatched episodes may remain missing. Full SickChill parity remains incomplete.
