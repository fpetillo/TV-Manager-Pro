# TV Manager v18.2.6 — Real No-Wait Show Detail Hotfix

This release addresses a case where Show Detail still appeared to hang even though a progress indicator was displayed.

## What changed

- Removed dependence on browser-generated global variables for DOM elements.
- Show Detail now paints a usable screen immediately before API calls return.
- Header, first episode page, season list, and counts are started as separate short requests.
- The first episode load now starts with a smaller page so large shows do not block the UI.
- The watchdog now replaces the episode table with retry/jobs/logs actions after about 1.2 seconds instead of leaving an animated bar on screen.
- Fetch options no longer pass the internal `timeout` value into the browser fetch call.

## Operational note

If the retry panel appears, another task is likely holding SQLite or the database is on slow storage. Open Active Jobs and Logs, stop any scan that is running, then retry 25 episodes.
