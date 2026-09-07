# Full-Library Metadata Refresh

Open **Library Health** and use the **Metadata Gaps** panel.

Recommended workflow:

1. Confirm `/api/metadata/status` shows TMDb configured.
2. Click **Preview full refresh**.
3. Start with **Stale only** checked for normal maintenance.
4. Use **Refresh whole library** when rebuilding metadata after a SickChill import.
5. Watch the progress indicator for processed, succeeded, and failed counts.

For large libraries, use a batch size between 5 and 15. This keeps TMDb traffic steadier and avoids holding database write locks during network requests.

Required `.env` setting:

```env
TMDB_BEARER_TOKEN=your_tmdb_read_access_token
```

or legacy v3 key:

```env
TMDB_API_KEY=your_tmdb_v3_key
```
