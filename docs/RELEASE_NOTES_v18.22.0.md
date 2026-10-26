# TV Manager v18.22.0 — Interface themes

Built on v18.21.0.

## What changed

TV Manager now has four interface themes:

| Theme | Look |
|---|---|
| **Classic** | The existing dark-blue look, unchanged. The default. |
| **Glassy** | Frosted, translucent panels with soft highlights over a violet, cyan and pink colour backdrop. The menu, page headers, cards and panels blur what is behind them. |
| **Midnight** | Near-black, neutral surfaces with the same gold and blue accents. |
| **Daylight** | A light theme: pale surfaces, dark text, the same accent buttons. |

**To choose a theme:** scroll to the bottom of the side menu and pick one under **Theme**. The page changes at once. The choice is saved on the server, so every browser and device opening TV Manager uses it. If saving fails, the page switches back and the picker's tooltip says why.

The theme is one setting (`ui` / `theme`) and can also be read or set with `GET /api/ui/theme` and `POST /api/ui/theme` with `{"theme": "glassy"}`. An unknown name is refused with HTTP 400.

## How it works

- `static/style.css` stays the Classic theme.
- `static/themes.css` holds the other themes. It is generated from `style.css` by `scripts/build_themes.py`, which copies every rule that sets a colour under `html[data-theme="<theme>"]` with the colour translated by that theme's rules (for example: dark surfaces become translucent in Glassy and pale in Daylight; light text becomes dark in Daylight; accent buttons keep their colours). Hand-written finishing touches (backdrops, glass blur, form controls) are added at the end of each theme.
- Every page sets `<html data-theme="...">` from the saved setting when it is rendered, so there is no flash of the wrong theme on load.
- After changing `style.css`, run `python scripts/build_themes.py`. A test fails if `themes.css` is out of date.

To add a theme later: add it to `THEMES` in `ui_themes.py`, add a colour function to `MAPPERS` and its finishing touches to `THEME_EXTRAS` in `scripts/build_themes.py`, and rebuild.

## Also fixed

The Settings page showed garbled characters where symbols belonged (for example `âŒ˜ Search TV Manager` instead of `⌘ Search TV Manager`, and `Runningâ€¦` instead of `Running…`). The page and its script had been saved with the wrong text encoding; both are repaired.

## Updating to 18.22.0

Same as 18.21.0: download `update-server.ps1` from the v18.22.0 tag and run it, as in [WINDOWS_SERVER_UPDATE.md](WINDOWS_SERVER_UPDATE.md). Then press **Ctrl+F5** once in each browser so it loads the new stylesheet.

## Validation

- 603 passed, 11 skipped on the Linux build host (Windows-only PowerShell, updater lock and service checks); the full suite also runs on GitHub's Windows runner.
- 8 new tests: theme API (default Classic, save, unknown name refused, saved value survives a restart), every page template and the script-free support pages load the theme stylesheet and carry `data-theme`, the menu picker lists all four themes with the saved one selected, `themes.css` is current and every selector in it is theme-scoped, colour-mapping rules, picker script reverts on a failed save, Settings text no longer double-encoded.
- Browser check in Chromium on a disposable copy with sample shows: Launchpad, Dashboard, Shows, a show page, Settings, Post Processing, Show Queue, Trakt, Jobs, About and Upcoming in all four themes; switching with the picker changes the page at once and survives a reload; no page errors.
- Not performed: a check in the browsers you use with the Windows server. Browsers without `backdrop-filter` support show Glassy without the blur (panels stay translucent).
