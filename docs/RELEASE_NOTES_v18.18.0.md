# TV Manager v18.18.0 — Flexible show-name matching in Post Processing

Built on v18.17.0.

## What changed

Post Processing matched the release title to a show only when the letters and numbers lined up exactly, so a show whose name has an apostrophe, ampersand, dash or dotted initials was often left unmatched. Release names are not under your control, so the title comparison now sets those differences aside:

| Show in TV Manager | Release names that now match |
|---|---|
| Grey's Anatomy | Greys.Anatomy, Grey’s Anatomy (curly apostrophe) |
| Law & Order: Special Victims Unit | Law.and.Order.Special.Victims.Unit, Law.&.Order… |
| Marvel's Agents of S.H.I.E.L.D. | Marvels.Agents.of.SHIELD, …S.H.I.E.L.D |
| Mr. & Mrs. Smith | Mr.and.Mrs.Smith |
| 9-1-1 / 9-1-1: Lone Star | 911, 911.Lone.Star |
| Spider-Man | Spiderman |
| Pokémon | Pokemon |
| The Handmaid's Tale | Handmaids.Tale (no leading The) |
| Doctor Who (2005), S.W.A.T. (2017), The Office (US) | Doctor.Who, SWAT.2017, S.W.A.T, The.Office.US, Office |
| Shameless | Shameless.US |

The rules, applied to both the show title and the release title before the SxxEyy marker (from the file name, then the release folder):

- apostrophes are removed, straight or curly;
- `&` and `+` read as "and";
- dashes, dots, colons and other punctuation are separators, and spacing can differ (Spider-Man/Spiderman, 9-1-1/911);
- dotted initials join up (S.H.I.E.L.D. = SHIELD);
- accents are ignored;
- a leading "The" may be missing;
- a year or country in the show title, such as (2005) or (US), may be missing from the release, and a release may add one.

The safety rules stay:

- An exact match still wins over a looser one, so "Doctor Who" and "Doctor Who (2005)" each get their own releases.
- Two shows that match equally well are blocked as ambiguous, for example The.Office with both (US) and (UK) in the library.
- Short titles such as ER, From and Friends still match only the whole title, never part of a longer one.
- A release with extra words after a show title is not taken for that show unless the extra words are a year or country, so Law.And.Order.SVU is not filed under Law & Order. Add an alias to the show for abbreviations like that.

## Validation

- 558 passed, 11 skipped (Windows-only PowerShell, updater lease and service checks on the Linux build host).
- New tests cover 30 real-world release names against a 23-show library, plus the ambiguous-edition, extra-words, exact-beats-edition and folder-name cases. The earlier ER/From/Friends tests still pass.
- End-to-end run on a disposable copy: Greys.Anatomy, Law.and.Order.Special.Victims.Unit and a Marvels.Agents.of.SHIELD release folder were all matched and moved into the right show folders.
