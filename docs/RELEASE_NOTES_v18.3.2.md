# TV Manager v18.3.2 - Post-Processing Safe Show Matching Hotfix

This hotfix corrects a dangerous post-processing rename issue where short or common show titles could be matched from inside longer release names.

## Fixed

- `Friends.from.College.S01E03...` no longer matches the show `FROM`.
- `Friends.S03E10.The.One.Where.Rachel.Quits...` no longer matches the show `ER`.
- Post-processing no longer chooses a show simply because the show name appears somewhere in the full path or release title.

## New matching rules

- TV Manager extracts the normalized release title before the season/episode marker.
- Exact title-prefix matches win.
- Short/one-word titles require an exact prefix match.
- Long multi-word aliases can still match release prefixes with a lower confidence score.
- Low-confidence or ambiguous matches are rejected before any move/copy/hardlink operation.

## Operator guidance

Always run **Preview Folder** before processing. The Decision column now includes match confidence and the reason used to approve the show match.
