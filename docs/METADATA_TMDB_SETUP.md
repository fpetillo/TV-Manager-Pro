# TMDb Metadata Setup

TV Manager uses TMDb for show posters, overview text, episode names, season information, and external IDs.

## Recommended configuration

Add a TMDb API Read Access Token to `.env`:

```env
TMDB_BEARER_TOKEN=your_tmdb_api_read_access_token
```

TV Manager also supports legacy TMDb v3 API keys:

```env
TMDB_API_KEY=your_legacy_tmdb_v3_api_key
```

Accepted environment names are:

- `TMDB_BEARER_TOKEN`
- `TMDB_READ_ACCESS_TOKEN`
- `TMDB_V4_TOKEN`
- `TMDB_API_KEY`
- `TMDB_V3_API_KEY`
- `THEMOVIEDB_API_KEY`

## Imported SickChill settings

If a SickChill import brings over a TMDb key, TV Manager can use that saved setting as a fallback when `.env` does not contain a key. Environment values still take priority.

## Checking status

Open:

```text
http://127.0.0.1:5050/api/metadata/status
```

The API reports whether TMDb is configured and where the active credential was found, without displaying the actual secret.

## 401 Unauthorized

A 401 means TMDb rejected the credential. Confirm that you copied the full TMDb API Read Access Token into `TMDB_BEARER_TOKEN`, or place the legacy v3 key in `TMDB_API_KEY`. Restart TV Manager after editing `.env`.
