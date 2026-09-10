## 18.5.14 — Aired episode queue progress

Show Queue now counts only episodes with a valid airdate on or before today (server local date). Future and unknown dates no longer inflate downloaded/total, missing counts or missing episode numbers. Season summaries show missing / aired totals; fully unaired seasons are omitted. Ignored and globally excluded Specials remain excluded. Recorded file paths remain the downloaded criterion; no disk scan is performed. Future shows remain listed with No aired episodes, and Next Ep retains upcoming information.

Default sorting prioritizes missing share of aired episodes, then missing count. The Sort by Missing / Aired button restores that priority; the Downloads column retains count-based sorting. Sorting happens before pagination. This ratio priority is a TV Manager design choice, not a claim that SickChill has the identical comparator.

Research: SickChill describes Downloads as downloaded versus aired episodes in https://github.com/SickChill/sickchill/wiki/Remaining-settings-explained and ignored episode exclusion in https://github.com/SickChill/sickchill/wiki/Episode-Status .

Validation: 307 tests passed and JavaScript/whitespace checks passed. API regression covers partial and future-only shows, unknown dates, ordinal imported dates, ignored/S00 exclusions, per-season counts and sorting before pagination. Isolated browser shows S01 1/1 missing with future S02 excluded. No production data changed. Restart and refresh Show Queue. Full SickChill parity remains incomplete.
