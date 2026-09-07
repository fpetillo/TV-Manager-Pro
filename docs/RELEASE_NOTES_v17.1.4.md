# TV Manager v17.1.4 Release Notes

## Route hardening fix

This patch fixes real-world navigation failures reported for the Library Health and About pages.

- `/library-health` now has trailing-slash and alternate route aliases.
- `/library-health` has a server-rendered fallback page if the template or JavaScript layer fails.
- `/about` now has trailing-slash and `/version` aliases.
- `/api/version` and `/api/about` support trailing slashes.
- `/api/library/health-report` supports trailing slash and `/api/library-health/report`.

The goal is that support/version pages always display something useful instead of a blank page, redirect loop, stale cached page, or 404.
