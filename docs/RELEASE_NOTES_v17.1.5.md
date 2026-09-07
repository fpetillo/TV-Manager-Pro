# TV Manager v17.1.5

Emergency route-registration hardening build.

## Fixed

- Added `/routes` and `/api/routes` diagnostics to show the actual Flask route map.
- Added a startup required-route check in `server.py` so production startup fails fast if About or Library Health routes are missing.
- Added a 404 fallback page that explains when an older running install is serving requests.
- Made `/about`, `/library-health`, `/api/version`, `/api/about`, and related aliases public/local support routes.

## Operator note

If `/about` or `/library-health` still show the plain Flask "Not Found" page after this update, the running process is not using the updated folder. Stop the server, confirm `VERSION` is 17.1.5, and start it again from that same directory.
