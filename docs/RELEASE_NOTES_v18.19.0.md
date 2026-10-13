# TV Manager v18.19.0 — Episode search finds the right show

Built on v18.18.0.

## What changed

Searching for an episode of a show with a common word for a name, such as **Brothers**, returned Band of Brothers, Brothers & Sisters and The Brothers Sun, and could download one of them. The indexer matches any title containing the word, and TV Manager only checked titles when it fell back to a reworded search name, never on the first search.

Every episode and season-pack search result is now checked: the release title must be the show's name followed by the episode number. Other results stay in the list, marked rejected with "Not this show or episode", so you can see what the indexer returned.

| Show | Accepted | Rejected |
|---|---|---|
| Brothers (first aired 2009) | Brothers.S01E01, Brothers.2009.S01E01 | Band.of.Brothers.S01E01, Brothers.and.Sisters.S01E01, The.Brothers.Sun.S01E01, Brothers.1984.S01E01 |
| Doctor Who (2005) | Doctor.Who.S01E01, Doctor.Who.2005.S01E01 | |
| The Office (US) | The.Office.US.S01E01, Office.S01E01 | |
| Law & Order | Law.and.Order.S01E01 | Law.and.Order.SVU.S01E01 |

Matching ignores punctuation, spacing, apostrophes, & versus "and", accents and dotted initials (the same rules Post Processing uses since 18.18.0). A release may drop a leading "The" or a year/country that is part of the show's name, and may add the show's first-air year. A different year, a country tag that is not in the show's name, or any other extra word means a different show.

## New show settings (Edit show settings)

- **Release title matching**: *Strict* (default) checks every title as above. *Loose* accepts whatever the indexer returns for the show name, as before; reworded fallback searches are still checked.
- **Extra search names** (one per line): searched after the show name and accepted as this show. Use it when releases use another title, a country tag or an abbreviation, for example `Brothers US`. Extra names are per show and are not saved into new-show defaults.
- **Search indexers by TVDB/IMDb/TMDB ID when supported** (on by default): when the show has an ID and the indexer advertises ID search for TV, TV Manager searches by ID first, which returns only that show. If the ID search fails or finds nothing usable, the name search runs as before. Not used for air-by-date, sports or anime shows.

## Validation

- 579 passed, 11 skipped (Windows-only PowerShell, updater lease and service checks on the Linux build host).
- 21 new tests: the Brothers case end to end (wrong shows rejected, the right release downloaded, nothing downloaded when only other shows are found), loose mode, extra names, ID search first, ID search off, unsupported IDs not sent, failed ID search falling back, 11 title-matching cases, first-air year, season packs, and setting validation.
- Real HTTP run against a stand-in Newznab indexer: name search rejected Band of Brothers and Brothers and Sisters; ID search sent `tvdbid` without the name.
- Browser check on a disposable copy: the show settings dialog shows the new fields and saves them, no page errors.
- Not performed: search against your real indexers, and installation on the server.
