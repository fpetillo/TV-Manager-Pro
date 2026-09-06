# SickChill Migration Guide

1. Back up the existing SickChill database and configuration.
2. Start TV Manager and open **Migration**.
3. Import the SickChill SQLite database.
4. Import SickChill `config.ini`.
5. Review **Operations → Root & Path Health**.
6. Add path mappings if downloader/library paths differ.
7. Run **Library Conflicts**.
8. Enable **Simulation Mode**.
9. Test providers and download clients.
10. Review Missing/Upcoming and a representative set of shows.
11. Disable Simulation Mode only after search choices look correct.
12. Create a configuration snapshot named `Known Good After Migration`.

Imported secret values remain stored locally and are masked in the UI.


## Upgrading to v14
1. Keep the existing `tvmanager.db` and configuration files.
2. Replace the application source with the v14 release.
3. Start TV Manager normally.
4. v14 creates a one-time SQLite online backup under `backups/` before applying the v14 schema migration.
5. The migration adds acquisition events, upgrade replacement records, subtitle retry metadata, and schema migration version 14.
6. Startup runs `PRAGMA quick_check` after migration and stops rather than silently continuing if integrity validation fails.

The release ZIP never contains `tvmanager.db`, `.env`, `config.ini`, logs, diagnostics, backups, or managed-trash media.

## Upgrading to v15
v15 creates a one-time online database backup before adding `media_fingerprints` and `scheduler_leases`. Existing SickChill naming settings are not rewritten; they are now actively honored by post-processing.

The release contains no runtime database, `.env`, imported `config.ini`, backups, diagnostics, logs, or managed-trash media.

## Upgrading to v16
v16 creates a one-time online database backup before adding administrator/security tables, naming preset storage, and metadata refresh state.

Existing localhost installations do not suddenly require a password. Browser authentication remains opt-in until enabled locally. Remote/LAN requests, however, are blocked until security is configured.
