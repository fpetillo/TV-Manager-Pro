# TV Manager 18.5.8 - Season download progress

Collapsed season headings show downloaded and total episodes, for example 18 of 24 episodes downloaded. Uses the existing with_files aggregate, consistent with Show Queue: downloaded means an episode has a recorded nonempty library file path. This is not a fresh disk accessibility scan. Totals include ignored episodes and Specials and remain full-season totals when filters are active.

Validation: 300 tests pass and JavaScript syntax passes. Regression checks partial, complete and zero downloads. Live Friends browser verified Season 3 shows 15 of 25 and Season 6 shows 22 of 23, while collapsed. No media/status changes. Reopen Show Detail for the static update; normal restart updates the runtime version label.
