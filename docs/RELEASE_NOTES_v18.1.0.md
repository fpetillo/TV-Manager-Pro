# TV Manager v18.1.0 — SickChill Queue Counts & Season 00 Ignore

Version 18.1.0 tightens the download/show queue workflow so it behaves more like SickChill when deciding which shows need attention.

## Queue count behavior

- The Show Queue **Missing / Downloads** column now sorts SickChill-style:
  1. missing episode count
  2. downloaded episode count
  3. total episode count
  4. completion percent/show name fallback
- Queue rows now show missing episode numbers, such as `S03E01, S03E02`.
- Queue rows show downloaded totals alongside missing totals.
- The Download Queue page now sorts by missing work first, then downloaded totals.

## Season 00 / Specials option

A new setting is available under **Settings → Automation / Search defaults**:

> Ignore Season 00 / Specials in show counts, missing totals, and progress meters

When enabled, Season 00 episodes stay in the database but are excluded from:

- show episode totals
- missing episode counts
- downloaded totals
- Show Queue progress meters
- Download Queue count display and triage sorting
- queue APIs that report missing/downloaded totals

## API behavior

- `GET /api/show-queue` now returns `ignore_season_zero_counts`, `missing_episode_numbers`, and `missing_display`.
- `GET /api/queue/unified` now returns `missing_total`, `downloaded_total`, `episode_total`, `download_percent`, `missing_episode_numbers`, and `ignore_season_zero_counts`.
- `POST /api/settings/tvmanager` accepts `ignore_season_zero_counts`.
- `GET /api/tvmanager/config` returns `ignore_season_zero_counts`.

## Operator result

The operator can now see which exact episodes are missing and sort queues by shows that need the most completion work, while optionally excluding specials from normal completion math.
