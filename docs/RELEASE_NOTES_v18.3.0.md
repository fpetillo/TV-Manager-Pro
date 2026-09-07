# TV Manager v18.3.0 — SickChill Parity Audit and Online Help

## Highlights

- Adds in-app Help Center at `/help`.
- Adds SickChill parity matrix with statuses for major replacement features.
- Adds workflow guidance for common operator tasks.
- Adds contextual help topics for Show Queue, Download Center, Episode Management, Ignore Rules, Post Processing, Subtitles, and Troubleshooting.
- Adds API endpoints for help and product workflow mapping.
- Adds Help Center navigation under Administration and the nav footer.

## New APIs

```text
GET /api/help
GET /api/help/<slug>
GET /api/help/sickchill-parity
GET /api/product/workflow-map
```

## Notes

The parity matrix is intentionally honest. Provider-specific depth, subtitles provider automation, media server provider depth, and anime/scene/XEM parity remain visible improvement areas.
