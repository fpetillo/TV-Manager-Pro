# TV Manager v17.3.4

Import Center reliability patch.

## Fixed

- The Import Center now detects HTML or text returned from an API endpoint and shows a useful operator error instead of `Unexpected token '<'`.
- API exceptions now return JSON for `/api/*` routes so JavaScript callers can display the real failure.
- Added trailing-slash compatibility for SickChill import job endpoints.
- Hardened background import job startup error handling.

## Validation

- Existing test suite passes.
- Added regression checks for import progress JSON safety and API error handling.
