# TV Manager v18.3.1 — Global Specials Missing/Wanted Control

This patch makes Season 00 / Specials behave the way Frank requested: they do not appear in Missing/Wanted workflows unless explicitly re-enabled.

## What changed

- Changed the default `TVManager / ignore_season_zero_counts` value to enabled.
- Added one-place global controls in Manage → Season 00 / Specials.
- Added global preview, ignore, and include background actions.
- Added a hard search guard so S00/Specials are not searched while the global rule is enabled.
- Updated Missing, Wanted, Backlog Overview, Show Queue, Download Queue, dashboard wanted counts, and search eligibility to respect the global S00/Specials policy.
- Global ignore persists episode-level ignored flags and reason text.

## New APIs

```text
POST /api/episodes/specials/global-preview
POST /api/episodes/specials/global-ignore/start
POST /api/episodes/specials/global-include/start
```

## Operator result

S00/Specials stay visible in episode lists for review, but they no longer pollute Missing/Wanted or queue status.
