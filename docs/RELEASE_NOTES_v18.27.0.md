# TV Manager v18.27.0 — Browser icon

Built on v18.26.0.

## What changed

TV Manager now has its own icon: a blue TV screen with a play button on a dark rounded square.

- It shows in the browser tab, bookmarks and history on every page, including the login page.
- On a phone, **Add to Home Screen** uses it (180 px Apple touch icon; 192 and 512 px icons in the web app manifest).
- `/favicon.ico` (16, 32, 48 and 64 px) and `/site.webmanifest` are served without logging in, so the icon also shows before sign-in. The server log no longer records a 404 for `/favicon.ico` on every page load.

Files: `static/icons/tv-manager.svg` (source), `favicon.ico`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`; icon links added to all 39 page templates.

## Updating to 18.27.0

Download `update-server.ps1` from the v18.27.0 tag and run it, as in [WINDOWS_SERVER_UPDATE.md](WINDOWS_SERVER_UPDATE.md); start TV Manager with run.ps1. Browsers cache icons: if the old blank icon stays, press Ctrl+F5 or close and reopen the tab.

## Validation

- 3 new tests: icon files and sizes, the icon links in every page template, and `/favicon.ico`, `/site.webmanifest` and the SVG served with browser login turned on.
- Chrome on a disposable copy: the page declares the four icon links, the SVG icon loads (200) and the server log has no 404s.
