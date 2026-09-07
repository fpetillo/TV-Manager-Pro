# TV Manager 18.5.1 - DVD scene mapping guard

Automatic XEM mappings use aired episode numbering. DVD-order shows now reject refresh with a clear explanation and ignore cached aired mappings during searches and completed-file matching. Explicit manual scene overrides continue to work. Refresh also rechecks episode order before saving its response.

Validation: 292 tests passed, including a DVD-order fixture with a stale aired cache, canonical fallback and manual override. No UI changes. No live integration certification. Restart after active jobs finish to activate. Full SickChill parity remains incomplete.
