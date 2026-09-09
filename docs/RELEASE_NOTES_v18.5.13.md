## 18.5.13 — Editable configuration center

Settings now exposes All Configurable Settings, combining stored/imported configuration with a catalog of 64 literal application defaults extracted from current configuration readers. Sections and fields can be filtered; only changed fields are saved, and failed saves report the error and count already saved. Protected inputs use password fields and unchanged masked values are not resubmitted. Library roots direct users to Library Locations to retain shows-in-use validation.

Settings navigation now links to Library Locations, Quality Profiles, Metadata Sources, Native Notifications, Providers/Media Servers/Webhooks, Post-Processing, New Show Defaults and Database Protection. Client/provider/notification summary tabs have edit shortcuts. Search-default saves check HTTP success. Unsupported legacy SickChill settings remain editable but do not imply native behavior or full parity.

Validation: 306 tests passed; JavaScript syntax and whitespace checks passed. New regression verifies unsaved default discovery and stored override persistence without duplicates. Isolated browser edited recent_days from 14 to 21, saved and reopened to verify persistence. No production settings changed.

Restart TV Manager and refresh Settings. Startup-only options require a restart after editing. The catalog must be updated when new literal configuration readers are added; structured settings continue to use their linked dedicated editors.
