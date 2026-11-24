# TV Manager v18.32.0 — Plex scans with no setup

Built on v18.31.0.

## What changed

- After each movie import (and after moving earlier imports), TV Manager asks **every enabled Plex server to scan all of its movie libraries**. Each Plex server already knows its libraries and their folders, so nothing has to be configured in TV Manager. TV libraries are never scanned for a movie. Plex only reads new or changed files, so the scan is quick.
- The per-server "folder translation" setting from v18.31.0 is removed, with its screen and saved value.
- The activity entry for each import names the destination and each server's result, e.g. "Media servers — Den: scanning 2 movie libraries; Office: scanning 1 movie library."
- Movie destination folders (v18.31.0) are unchanged: you choose where movies go, written the way the TV Manager server reaches them.

## After updating

Movies › Settings › *Where new movies go*: enter the destination folder(s), Save, and use **Move N movies into the destination folders** for earlier imports.

## Validation

- Test: two Plex servers, each asked to refresh both movie sections and never the TV section, with no configuration; scan note per server.
- Full suite green.
