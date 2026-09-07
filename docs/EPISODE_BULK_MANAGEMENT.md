# TV Manager v18.2.0 — Bulk Episode Management & Ignore Rules

Version 18.2.0 adds SickChill-style episode management for operators who need precise control over what TV Manager considers wanted, missing, searchable, and complete.

## Why this matters

TV metadata often includes Season 00 specials, recaps, trailers, behind-the-scenes clips, interviews, web extras, duplicate guide entries, and other episodes that an operator does not want TV Manager to search for or count as missing. Version 18.1.0 added a global Season 00 count option. Version 18.2.0 adds the stronger, episode-level management layer.

## Episode-level ignored flag

Episodes can now be marked ignored/not considered while remaining visible in the database.

Ignored episodes are excluded from:

- Show Queue missing counts
- Download Queue wanted/missing totals
- SickChill-style backlog searches
- Recent/backlog search eligibility
- Completion/progress meters that use considered counts
- Missing episode number displays

Ignored episodes remain visible so operators can audit and re-include them later.

## Show Detail bulk controls

The Show Detail episode list now includes bulk controls:

- Select Page
- Clear
- Ignore Selected
- Include Selected
- Set Wanted
- Set Downloaded
- Unmonitor
- Ignore S00 Specials
- Include S00 Specials
- Ignore Filtered Missing

Each episode row includes:

- selection checkbox
- status selector
- monitored checkbox
- ignored checkbox
- ignored reason/note visibility
- disabled search button for ignored episodes

## Manage page bulk controls

Manage → Episode Status Management now includes filters and actions for large changes:

- show
- season
- current status
- aired only
- missing only
- Season 00 / Specials only
- ignored only
- preview matching episodes
- apply status
- ignore matching
- include matching

## New APIs

```text
POST /api/episodes/bulk/preview
POST /api/episodes/bulk/apply/start
POST /api/shows/<show_id>/specials/ignore/start
POST /api/shows/<show_id>/specials/include/start
```

## Database additions

The `episodes` table now supports:

```text
ignored INTEGER DEFAULT 0
ignored_reason TEXT
ignored_at TEXT
ignored_source TEXT
managed_note TEXT
```

A new `episode_management_history` table records bulk actions.

## Operator rule

Ignored does not mean deleted. It means the episode is intentionally excluded from wanted/missing/search/count logic.
