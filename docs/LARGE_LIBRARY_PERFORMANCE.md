# Large Library Performance

TV Manager is designed to replace SickChill on real media servers, including systems with very large historical libraries.

## Library loading

The Shows API uses server-side pagination:

```text
GET /api/shows?limit=100&offset=0
```

The response includes:

- `results`: current page of shows
- `count`: number of shows in the current page
- `total`: total matching shows
- `limit`: page size used by the server
- `offset`: starting offset
- `next_offset`: next page offset or null
- `has_more`: whether more rows are available

## Why this matters

Large SickChill imports can contain tens of thousands of show/episode records. Returning all show rows at once makes browsers appear frozen. TV Manager now loads the first page immediately and lets the operator continue in controlled chunks.

## Recommended operator workflow after import

1. Open `/api/import/verify?recover=1` to verify active database counts.
2. Open `/manager`.
3. Use search/status/group filters to narrow the library.
4. Use **Load next** only when browsing beyond the first page.
5. Use `/library-health` to find missing files, duplicate groups, and metadata gaps.
