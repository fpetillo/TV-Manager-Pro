# TV Manager v17.9.1 - TMDb Metadata Authentication Reliability

This maintenance release fixes a metadata-refresh regression where TMDb calls could return raw `401 Client Error: Unauthorized` messages after recent workflow changes.

## Fixes

- Metadata refresh now uses one shared TMDb client.
- Supports TMDb v4 Read Access Tokens via `TMDB_BEARER_TOKEN`.
- Supports legacy TMDb v3 API keys via `TMDB_API_KEY`, `TMDB_V3_API_KEY`, or `THEMOVIEDB_API_KEY`.
- Falls back to imported/saved SickChill TMDb settings when available.
- TMDb 401/403 responses are returned to the UI as clear operator-facing JSON errors.
- Added `/api/metadata/status` for safe credential-status diagnostics.
- Fixed metadata batch invocation compatibility for `batch_size`.

## Operator guidance

For best results, put one of these in `.env`:

```env
TMDB_BEARER_TOKEN=your_tmdb_api_read_access_token
```

or:

```env
TMDB_API_KEY=your_legacy_tmdb_v3_api_key
```

Then restart TV Manager and check:

```text
http://127.0.0.1:5050/api/metadata/status
```

The response shows whether TMDb is configured and the credential source, without exposing the secret value.
