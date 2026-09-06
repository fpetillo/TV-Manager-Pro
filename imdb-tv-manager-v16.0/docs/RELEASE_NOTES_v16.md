# TV Manager 16.0 Release Notes

## Browser and LAN security

TV Manager remains local-first. A default localhost installation continues to work without forcing a login.

v16 adds an administrator account and browser-authentication option for users who want to access TV Manager from another PC.

Security features include:

- PBKDF2-HMAC-SHA256 password hashing with a unique random salt.
- Minimum 12-character administrator passwords.
- Login sessions backed by a persistent random application session key.
- CSRF validation for authenticated browser `POST`, `PUT`, `PATCH`, and `DELETE` requests.
- Five-failure / 15-minute login throttling per remote address.
- Security event history.
- `X-Content-Type-Options`, frame, referrer, and permissions headers.
- Existing bearer API tokens remain supported for integrations.
- Bearer-token API usage is recorded in `api_access_log`.

When browser authentication is disabled, only loopback clients receive the compatibility bypass. Remote/LAN clients are rejected.

The Waitress production server refuses a non-loopback `HOST` unless an administrator account exists and browser authentication is enabled.

## Naming configuration UI

Settings now includes a Naming section with:

- SickChill Default preset.
- Compact preset.
- Show + Episode preset.
- Scene-style preset.
- Editable naming pattern.
- Rename toggle.
- Associated-file toggle.
- Live multi-episode preview.

The existing v15 naming engine remains the source of truth, so the preview is the same renderer used by post-processing.

## Real scheduled post-processing

The `post_processing` scheduler job now follows the imported SickChill configuration:

- `process_automatically=1` and Simulation Mode off → live processing.
- `process_automatically=0` → preview/dry-run.
- Simulation Mode on → preview/dry-run regardless of legacy setting.

This lets migrated SickChill installations regain automatic post-processing without silently arming it during migration.

## Real scheduled metadata refresh

The metadata scheduler now selects stale, enabled, unpaused shows in a small configurable batch.

Per-show state is stored in `metadata_refresh_state`.

Network metadata and season requests are completed before TV Manager opens the SQLite write transaction, avoiding long database writer locks during remote requests.

The default metadata batch size is three shows per run and can be changed through `TVManager.metadata_batch_size`.

## Existing-library scan

Show library scans now recognize multi-episode files such as `S01E01E02` and mark each represented episode as downloaded.
