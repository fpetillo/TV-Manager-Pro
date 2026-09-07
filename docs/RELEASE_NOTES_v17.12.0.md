# TV Manager v17.12.0 — Full Metadata Refresh + Show Queue Date Fix

This release adds an operator-controlled full-library metadata refresh and fixes Show Queue episode date formatting.

## Full-library metadata refresh

Library Health now includes a full metadata refresh workflow:

- preview the number of shows that will be refreshed;
- run the refresh as a background job;
- see percent complete, processed count, success count, failure count, and current show;
- use a configurable batch size;
- optionally refresh stale shows only;
- validate TMDb configuration before starting.

New endpoints:

- `POST /api/metadata/refresh/full/preview`
- `POST /api/metadata/refresh/full/start`
- `GET /api/metadata/refresh/full/jobs`
- `GET /api/metadata/refresh/full/jobs/<job_id>`

## Show Queue date formatting

The Show Queue now normalizes imported/legacy episode air dates and displays Next Ep / Prev Ep in a readable date format. The API returns normalized ISO dates and the UI renders them as `M/D/YYYY`.

## Notes

A full refresh against a very large library can take a long time because every show may require multiple TMDb requests. Run it from the Library Health page while TV Manager remains open.
