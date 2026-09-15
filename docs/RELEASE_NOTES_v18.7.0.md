# TV Manager v18.7.0 — Recovery, processing and downloader coverage

This release closes several missing local workflows and improves download and installation reliability. Full SickChill parity remains incomplete: 15 locally complete and 17 partial feature families. See [the current audit](SICKCHILL_PARITY_AUDIT.md) and [protocol coverage](DOWNLOADER_PROTOCOLS.md).

## What changed

- Database Safety previews database/ZIP backups, optionally pairs restorable configuration snapshots, and queues confirmed restoration for restart. Previous files are preserved; failed startup rolls back on the next launch. Automation pauses after restoration. An offline recovery helper is available when the UI cannot start.
- Post Processing stages ZIP/RAR downloads with path/link/collision/size/time/space checks, then uses normal episode approval. Archives are preserved and processed members remembered. Configured scripts receive final file, original file, indexer ID, season, episode and air date. Script failures are reported while retaining successfully imported media.
- Added both SickChill symbolic-link directions alongside Move, Copy and Hardlink. Link methods require OS permission and never silently fall back to Move. Uncommitted transfers can be undone on failure.
- Manual jobs retain history and interrupted progress across restart. Durable handoff records prevent automatic resubmission after uncertain responses and season-pack overlap. Download Center provides reconciliation controls.
- Added native uTorrent, rTorrent HTTP XML-RPC and Synology Download Station. qBittorrent HTTP torrents have a reliable identity; Deluge uses magnet/file-specific methods; blackhole folders receive actual descriptor contents.
- Upcoming has a month calendar and iCalendar feed. Revocable private links grant calendar-only access. Air dates are all-day; precise broadcast timezone/time metadata remains outstanding.
- Known settings have choices, On/Off controls and numeric limits. Download Clients has visible edit entry points. Structured settings link to their editors; imported options with unverified behavior remain identified.
- Packaged Windows launches use the persistent installation directory for data and assets. Archive workers run independently of the server lease. Build staging excludes runtime data/secrets. The installer uses a writable per-user destination, executable shortcut and current version.

## Verification

Final automated counts are recorded in RELEASE_MANIFEST.json. Browser checks used a synthetic one-show, 35-episode installation: archive preview → approval → import → script; repeated scan with no new files; backup preview → confirmed stage → restart → completed restore; unresolved handoff release; calendar navigation; and typed settings save. The clean-install test exercises actual Flask routes, CSRF, signed restore-token rejection and calendar token scope/revocation.

A clean Windows executable was built and launched on an isolated port. Routes/assets used its installation directory. Its RAR worker extracted a 2,048-byte member from the upstream rarfile project's compressed RAR5 solid fixture while the server ran. Source extraction of both fixture members also passed. Fixture binaries are not committed. Two live symbolic-link tests are skipped because this account lacks permission. Downloader protocol tests use synthetic responses. The Inno Setup script is updated; installer compilation is not claimed.

## Restore instructions

In Database Safety, select a backup, click Preview Restore, review counts, type RESTORE and queue it. Restart TV Manager normally. Review downloader queues before arming automation again. Database restoration does not revert media files. Previous database/configuration files remain under the recovery folder.

If the UI cannot start, stop TV Manager and run the helper from its Python environment:

```text
python recover_library.py preview --backup "FULL BACKUP PATH"
python recover_library.py stage --backup "FULL BACKUP PATH" --confirm RESTORE
```

A normal launch applies the staged restore. Use `status` to inspect or `cancel` to withdraw a pending restore. Keep recovery folders until their contents have been checked.

## Activation and limits

Restart TV Manager normally and refresh pages after installing the source update. Publication is separate from live activation. Production media, credentials and configuration were not used as test fixtures.

Still open: site-specific providers; Deluge daemon, MLDonkey and put.io; AniDB; existing-show source/DVD-order migration; complete XEM/anime, subtitle/notifier and NFO/artwork coverage; broadcast timezone/time metadata; comprehensive imported-setting behavior; live external-service and platform acceptance. This is substantial progress, not a full-parity certification.
