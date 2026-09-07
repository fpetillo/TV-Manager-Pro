# TV Manager v17.1.2 Release Notes

## Library Health reliability fix

v17.1.2 fixes and hardens the Library Health page introduced in v17.1.

### Fixed

- Library Health now loads with a visible success/error status message instead of failing silently.
- The health API is defensive against empty, partially migrated, or legacy-imported databases.
- Missing episode files now means paths that exist in the database but are no longer present on disk.
- Episodes with no file path are tracked separately as `episodes_without_file_location`.
- Duplicate detection now works even if the fingerprint table exists before all optional joins/columns are available.
- The Library Health JavaScript is cache-busted by version so browsers do not keep an older broken script after upgrades.

### Added

- Separate Library Health panel for episodes without a file location.
- Separate Library Health panel for shows without folder paths.
- Schema warning cards when health checks are skipped because an older database lacks expected tables or columns.
- Stronger frontend error handling for metadata refresh and duplicate-cleanup preview/apply actions.

### Validation

- Full Python test suite passes.
- JavaScript syntax check passes for `static/library_health.js`.
