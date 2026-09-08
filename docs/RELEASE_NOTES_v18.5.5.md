# TV Manager 18.5.5 - Job status filters

Active Jobs provides All, Active, Queued, Running, Completed, Failed and Cancelled buttons with counts. Active includes queued/running; Completed maps to the actual complete status and Failed maps to error. Additional returned statuses receive their own buttons. Filtering is based on job status, not the failed-item counter within a completed job.

The chosen filter survives automatic refresh, zero-match views explain why no jobs are shown, and overlapping polls are avoided. Counts refer to the recent jobs returned by the existing API (currently up to 50), not lifetime history.

Validation: 296 tests pass plus JavaScript syntax. Browser verified live counts of 25 total / 23 completed / 2 failed and selection of Failed displays 2 of 25. Regression covers active grouping, exact statuses, additional statuses, changing counts and preserved selection. No jobs were started, cancelled or modified. Static fix available on reopening Jobs; runtime version label requires normal restart. Includes 18.5.4 collapsible season folders.
