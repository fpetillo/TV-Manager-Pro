# SickChill Cutover Checklist

Use this checklist when TV Manager is being installed on the same server that currently runs SickChill.

## 1. Prepare safely

- Keep SickChill running until TV Manager import and Library Health are validated.
- Back up SickChill's `sickbeard.db`, configuration file, and post-processing scripts.
- Install TV Manager side-by-side on a different port first.
- Do not point TV Manager at the live SickChill database; import from a copy.

## 2. Import and verify

- Open `/setup-assistant` and confirm the package, version, and startup scripts are present.
- Open `/import` and run Analyze.
- Review Preview results before writing anything.
- Run Import with the progress bar visible.
- Open `/api/import/verify?recover=1` and confirm shows and episodes are visible.

## 3. Health before automation

- Open `/library-health`.
- Resolve shows without folders.
- Resolve missing files and duplicate candidates.
- Confirm metadata IDs are present where possible.

## 4. Configure replacement operations

- Configure download clients and providers.
- Configure quality profiles and upgrade rules.
- Configure naming and post-processing folders.
- Configure backups, notifications, and server service startup.

## 5. Cut over

- Stop SickChill only after TV Manager health checks are acceptable.
- Start TV Manager as the production service.
- Watch logs and Library Health after the first automation cycle.
- Keep SickChill backup and rollback notes until the replacement is stable.
