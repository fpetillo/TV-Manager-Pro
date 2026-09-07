# TV Manager v18.0.0 - Professional Polish Release

Version 18 is the major polish/readiness release for TV Manager.

## Highlights

- Promotes the product line from v17.x to v18.0.0.
- Adds Launchpad Version 18 readiness checklist.
- Adds `/api/system/release-readiness` for install/runtime polish checks.
- Adds `release-and-push.ps1` to safely commit and push source updates from Windows.
- Adds GitHub release automation documentation.
- Refreshes Show Queue wording around numeric Downloads sorting.
- Updates navigation version identity to Version 18.
- Adds CSS polish for the readiness checklist, sort state, and Downloads meter.

## Source control safety

The included release script removes recursive PyInstaller output and generated folders before staging source files. It excludes private/runtime files including `.env`, `tvmanager.db`, logs, backups, imports, diagnostics, and generated installers.

## Validation

- Python compile check
- JavaScript syntax check
- Full pytest suite
- Package hygiene check
