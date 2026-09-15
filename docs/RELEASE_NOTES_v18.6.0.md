## 18.6.0 — Project review and reliability improvements

Corrected Show Detail header/season counts, duplicate episode handoffs, imported-date search eligibility, automatic-grab simulation enforcement, false-success job reporting and backup validation. Bulk missing searches can be stopped safely from Active Jobs, and completed download history no longer prevents searching again for a missing wanted episode. Search results from working providers remain visible when another provider fails.

The API job runner now respects background_worker_limit. Arming/pausing automation preserves individual scheduler choices. Case-insensitive setting edits preserve the original setting key. Backups reject empty/missing sources, use unique safe filenames and update the manifest atomically within the process.

Validation: 318 tests passed, 47 Python modules parsed, 38 JavaScript syntax checks passed, dependency consistency passed, and 41 isolated HTML page routes returned 200 with no broken literal template links. Browser checks verified cancellation, retained scheduler choices, correct show/season counts and partial provider results. Production media/settings were not changed and no downloads were submitted.

Full SickChill parity remains incomplete: the expanded catalog has 12 locally complete, 19 partial and one missing feature family. See [the full review](PROJECT_REVIEW_2026-09-15.md) for evidence, limitations and prioritized remaining work. Restart TV Manager and refresh open pages to activate the backend changes. Source publication is separate from live activation.
