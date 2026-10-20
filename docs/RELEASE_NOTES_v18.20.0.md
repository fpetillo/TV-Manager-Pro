# TV Manager v18.20.0 — Show Queue lists only what is missing

Built on v18.19.0.

## What changed

Under each show name the Show Queue listed every season, including seasons with nothing missing ("S01: 0/10 aired missing"), and showed "Missing: Complete" for complete shows. On a large library most of that text reported things that are not missing.

The Show Queue toolbar has a new **Details** selector:

| Choice | Under the show name |
|---|---|
| **Details: missing only** (default) | The "Missing:" episode list and only the seasons that have missing aired episodes. Complete shows show just their name. |
| **Details: all seasons** | Everything, as in 18.19.0: "Missing: Complete" and every season, including 0-missing seasons. |

Example for a show missing three episodes of season 3:

- Missing only: `Missing: S03E01, S03E02, S03E03` / `S03: 3/10 aired missing`
- All seasons: `Missing: S03E01, S03E02, S03E03` / `S01: 0/10 aired missing · S02: 0/10 aired missing · S03: 3/10 aired missing`

Your choice is remembered in that browser. The Missing / Downloads column, sorting, filters and counts are unchanged; S00 and ignored episodes follow the same rules as before.

## Validation

- 583 passed, 11 skipped (Windows-only PowerShell, updater lease and service checks on the Linux build host).
- 4 new tests run the real `show_queue.js` under Node: missing-only is the default and hides complete seasons and "Missing: Complete"; switching to all seasons restores them and saves the choice; a saved choice is used on the next visit.
- Browser check (Chromium) on a disposable copy of the app with synthetic queue rows: default shows only missing seasons, all seasons shows every season, the choice survives a reload, no page errors.
- Not performed: installation on the server.
