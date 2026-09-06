# Operations Guide

## Daily
Review Dashboard insights, Queue, Missing, provider health and failed downloads.

## Before configuration changes
Create a configuration snapshot and full database backup.

## Provider failures
The circuit breaker suspends repeatedly failing providers and retries later using exponential cooldown.

## Retention
Always use Preview first. Apply moves files into `managed_trash`; it does not permanently delete them.

## Diagnostics
System → Diagnostic Bundle creates a ZIP containing health data, operations data, redacted settings, schema and bounded logs.

## Windows startup
Run `install-startup.ps1` after validating the deployment. Use `uninstall-startup.ps1` to remove it.

## Acquisition recovery
Use Queue lifecycle history to distinguish downloader completion from library import completion. Blocked and Failed acquisitions are counted on Operations. Upgrade replacements stage old media under `managed_trash/upgrades`; rollback is available while that staged file exists.

## Duplicate-content scan
Operations → Library Conflicts includes a Content Duplicates scan. It fingerprints up to the requested library limit using file size plus first/last-MiB SHA-256 and caches the result until size or modification time changes.

System → Database & Scheduler Reliability exposes active scheduler leases and recent scheduler runs. Stale running records are changed to `Abandoned` at startup.

## v16 scheduler behavior
Scheduled post-processing is live only when the imported `process_automatically` value is enabled and Simulation Mode is off.

Metadata refresh selects only stale, unpaused, metadata-enabled shows and records each show's refresh status/error in `metadata_refresh_state`.
