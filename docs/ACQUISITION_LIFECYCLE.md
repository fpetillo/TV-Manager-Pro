# Acquisition Lifecycle

TV Manager 14 tracks downloads and season packs through an explicit lifecycle:

`Found → Queued → Downloading → Downloaded → Importing → Completed`

Failure/recovery states are `Failed`, `Blocked`, `Quarantined`, and `Superseded`.

Every transition is written to `acquisition_events`, so Queue can show how a release reached its current state.

## Safe upgrades

When post-processing identifies an episode that already has a media file, TV Manager compares the incoming release with the current release. A recognized downgrade is blocked. An equal-quality replacement must be a corrective `PROPER` or `REPACK`.

Before an accepted replacement is installed, the existing media file is moved to `managed_trash/upgrades/`. If the import fails, TV Manager attempts to restore the original automatically. Completed replacements remain available in Upgrade History for manual rollback while the staged file exists.

## Season packs

Season packs link to each missing episode they cover. Downloader state is tracked at the pack level, while completion requires every linked episode to be imported into the library.

## Queue

The Queue page combines episode downloads and season packs and exposes lifecycle history for each acquisition.
