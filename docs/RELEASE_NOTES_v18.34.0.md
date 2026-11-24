# TV Manager v18.34.0 — Hide downloaded movies in Discover

Built on v18.33.0.

## What changed

- Movies › Discover has a **Hide movies already downloaded** checkbox, like *Hide shows already in my library* on the TV discover page. The choice is remembered in the browser.
- Hidden: movies downloaded through Movies and movies found in the library scan (matched by title and year). Wanted or downloading movies stay visible with their status.
- When most of a TMDb page is already downloaded, further pages are read (up to 4) so the list is not left nearly empty, and a note says how many were hidden.

## Updating

Servers on 18.33.0 or later: `.\update-server.ps1`. Older servers: `.\update-server.ps1 -Version 18.34.0` once.

## Validation

- 4 tests: status shown by default; downloaded and library-matched movies hidden with page fill and correct next page; wanted movies kept; checkbox, saved choice and route parameter present.
- Chrome on a disposable copy: 4 results → 2 with the box ticked, note shown, choice remembered after reload.
