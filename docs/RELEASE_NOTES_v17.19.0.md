# TV Manager v17.19.0 — Downloader Validation Center

This release adds a dedicated downloader validation and monitoring workflow and clarifies Launchpad replacement-readiness messaging.

## Added

- New `/download-center` page.
- Downloader readiness panel.
- Background downloader connection test job.
- Background downloader queue poll job.
- Background download monitor refresh job.
- Recent download/handoff table.
- Accepted search-result handoff candidates with Send action.
- Recent downloader event table.
- Navigation link under Discovery & Search.

## Improved

- Launchpad now explains what "replacement readiness" means.
- Launchpad no longer leaves operators with an ambiguous loading message if the readiness API fails.
- Downloader handoffs continue through the existing `/api/search-results/<id>/grab/start` progress job and are visible in Active Jobs.

## Validation

- Python compile check for application modules.
- JavaScript syntax check for static scripts.
- Static release tests for the new downloader center, APIs, navigation, and Launchpad readiness UX.
