# TV Manager Operator Workflow

TV Manager is designed to replace SickChill with a guided operational flow rather than a collection of disconnected screens.

## Recommended workflow

1. Install TV Manager side-by-side with SickChill.
2. Copy the SickChill `sickbeard.db` database; never import directly from the live SickChill file.
3. Open **Workflow** for the command cockpit.
4. Open **Import Center** and run Analyze.
5. Run Preview and review skipped shows, warnings, duplicate candidates, and detected schema.
6. Run Import with the progress panel visible.
7. Open **Library Health** and resolve missing paths, duplicate groups, and metadata gaps.
8. Configure providers, download clients, naming, subtitles, automation, backups, and notifications.
9. Run side-by-side until results look correct.
10. Stop SickChill and cut over to TV Manager.

## Operator design principles

- Every risky action has a preview.
- Every import should produce visible progress and post-import counts.
- Library Health should explain what to do next, not just show numbers.
- The About, Routes, and System pages are support tools for confirming the running build.
- Duplicate cleanup moves files to managed trash rather than deleting directly.
