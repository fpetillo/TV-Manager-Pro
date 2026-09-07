# TV Manager v17.1.3 Release Notes

## About page reliability fix

- Fixed the About page so it is server-rendered and does not require JavaScript.
- Added a defensive fallback renderer for `/about` so a template problem does not leave the user with a broken page.
- Made `/about`, `/api/version`, and `/api/about` local-support endpoints that can show the installed version even before browser authentication is enabled.
- Added machine-readable `/api/about` details for support tooling.
- Added tests to verify the page returns HTTP 200 and visibly includes the current version.
