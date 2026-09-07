# TV Manager 18.4.0 — SickChill coverage audit and show preferences

This iteration fixes core behavior found during an upstream SickChill audit. It does not deliver full SickChill parity.

- Edit Show Settings opens a dialog in Show Detail and Library, with quality profile, metadata language, new-episode status defaults, subtitle enablement, and numbering/season preferences. Add-show folder selection includes these preferences.
- Profile selections retain their actual IDs. Manual episode search handles database rows correctly. Date/sports/scene/absolute-number queries and manual aliases are connected to provider search.
- Aired Unaired episodes become searchable. Subtitle scheduling respects the per-show switch and correctly splits configured language lists. Flat-library naming respects the season-folder setting.
- Scheduler leases use UTC consistently and acquire atomically. Torrent magnet hashes support hex and base32. Windows test fixtures close their databases correctly.
- Help Center replaces overstated parity claims with 29 feature families and explicit gaps. The audit document includes the upstream adapter inventory and acceptance work still needed.

Validation: 260 pytest tests passed, focused destination and missing-folder processing checks passed; all static JavaScript syntax and changed Python compilation checked. An isolated browser test saved and reopened show preferences (profile 4, fr-FR, Skipped, subtitles off, season folders off). Real external integrations are not certified by these tests.

Activation requires a normal TV Manager restart after active jobs finish. Production processing was not interrupted and no production show paths or media were changed. This source release is published to v17.0-dev and tagged v18.4.0.
