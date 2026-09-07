# TV Manager Progress Job Center

TV Manager v17.14.0 starts moving long-running operations into a shared progress-job pattern.

## Included in this release

- Library Health scan now runs as a background job with a visible progress bar.
- Database/config protection snapshot runs as a background job with progress.
- Full-library metadata refresh keeps its existing progress behavior.
- Import Center keeps its existing progress behavior.

## New shared job APIs

```text
GET /api/jobs
GET /api/jobs/<job_id>
```

Each job returns a consistent shape:

```json
{
  "job_id": "...",
  "kind": "library_health_scan",
  "status": "queued|running|complete|error",
  "stage": "Library scan",
  "message": "Scanning paths...",
  "percent": 35,
  "total": 0,
  "processed": 0,
  "succeeded": 0,
  "failed": 0,
  "errors": [],
  "result": {}
}
```

The goal is for every operation that can take noticeable time to show the operator a progress bar instead of freezing the page.
