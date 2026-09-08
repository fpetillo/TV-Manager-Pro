# TV Manager 18.5.7 - Collapsed season episode counts

Each season heading now displays its total episode count, including Specials and ignored episodes, without expanding the section. Counts use the existing per-show grouped season summary; full episode rows still load only when expanded. Search/status filtering inside expanded sections does not change the total badge.

Validation: 300 tests pass and JavaScript syntax passes. Existing startup regression now checks plural/singular counts while sections remain collapsed and episode pages are not requested. Live Friends browser verified Season 1 has 24 episodes, Season 3 has 25 and Specials has 39, all visible collapsed. No media or episode settings changed. Reopen Show Detail to load the static change; runtime version label updates on normal restart.
