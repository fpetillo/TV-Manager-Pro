# TV Manager v17.22.0 - Operations Progress Everywhere Audit

This release closes the Operations-page progress gap. Any Operations action that scans, checks, fingerprints, snapshots, or waits now starts as a monitored background job or shows a progress/activity panel.

## Added

- Background job endpoint for show folder scanning: `POST /api/shows/<id>/scan-library/start`.
- Background job endpoint for Root & Path Health: `POST /api/library/root-health/start`.
- Background job endpoint for Library Conflict Detection: `POST /api/library/conflicts/start`.
- Background job endpoint for Content Duplicate Fingerprinting: `POST /api/library/fingerprint-conflicts/start`.
- Background job endpoint for Configuration Snapshots: `POST /api/config-snapshots/start`.
- Operations page progress panels beside each scan/check action.
- Manager `Scan Existing Files` now displays progress and links to Active Jobs.

## Product rule

Any action that can take noticeable time must show progress, activity, a job link, or a clear working state.
