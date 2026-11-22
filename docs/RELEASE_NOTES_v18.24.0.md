# TV Manager v18.24.0 — Missing Episode Autopilot

Built on v18.23.0.

## What it does

**Autopilot** (side menu → Library → Autopilot) keeps the library complete without manual checking. Each run:

1. **Checks the download clients** for finished, failed and stalled downloads.
2. **Retries with a different release when a download fails or stalls.** The failed release is blocked, so it is never grabbed again, and the episode goes straight back into the search. A download that hasn't finished after the stall time (default 12 hours) counts as failed. After the set number of failed releases for one episode (default 5), the episode is **set aside for review** instead of being retried forever; **Retry** puts it back.
3. **Processes completed downloads** into the library (Post Processing).
4. **Searches missing episodes** and sends the best acceptable release to the download client. Episodes never searched go first, newest air date first, then the ones searched longest ago. An episode is not searched again within the retry time (default 24 hours), so a large backlog is worked through in rotation instead of retrying the same episodes.

**Missing means aired with no file:** the air date is today or earlier, the episode is monitored and not ignored, the show isn't paused and has searching on, and no download is already active. This now includes episodes marked **Skipped**, which is common after a SickChill import; before, only Wanted and Failed episodes were ever searched. The Specials (Season 00) rule in Settings still applies.

**Not aired yet:** episodes whose air date is in the future are never searched or counted as missing. On a show's page their file column now says **Not aired yet** (with the air date on hover) instead of **Missing**, and **No air date** when none is known.

## Turning it on

Open **Autopilot** and press **Turn on**. It arms automation if it was paused and runs on its schedule (default every 60 minutes). **Run now** starts a run immediately.

If no indexer is enabled for backlog searches, or no download client is set up, the page says so and runs skip the search. No episode is marked as searched, so nothing waits the retry time for a search that never happened. With **Simulation mode** on, searches run but nothing is sent.

## Settings (all on the Autopilot page)

| Setting | Default |
|---|---|
| Run every | 60 minutes (5 minutes to 7 days) |
| Episodes searched per run | 40 |
| Search the same episode again after | 24 hours |
| Give up on a download after | 12 hours |
| Releases to try per episode | 5 |
| Time limit per run | 30 minutes |
| Search episodes marked Skipped | On |
| Search Downloaded or Archived episodes whose file is gone | Off |
| Process completed downloads during each run | On |

The interval is also shown in **Settings → Automation** (`missing_autopilot`). Since 18.23.0, intervals set there survive restarts.

## Page

The Autopilot page shows:
- **counts:** missing (aired), due for a search, in the downloader, not aired yet, set aside, blocked releases;
- **settings;**
- **episodes set aside**, with Retry;
- **the last 10 runs:** searched, sent to the downloader, failed or stalled, time, errors.

## Also changed

- **Blocked releases are skipped at search time** (manual searches too). Before, a release on the failed-release list could still rank first, and the automatic grab then refused it, so nothing was sent even when another good release was available.
- The **Missing** page (`/api/missing`) uses the same definition as Autopilot, so it now lists aired Skipped episodes with no file and never lists not-aired ones.

## Updating to 18.24.0

Download `update-server.ps1` from the v18.24.0 tag and run it, as in [WINDOWS_SERVER_UPDATE.md](WINDOWS_SERVER_UPDATE.md). Then press **Ctrl+F5** in each browser, open **Autopilot**, check the settings and press **Turn on**.

On a SickChill-imported library the first runs may find many more missing episodes than before, because Skipped episodes are now included. Untick **Search episodes marked Skipped** if those were skipped on purpose.

## Validation

- 615 passed, 11 skipped on the Linux build host (Windows-only checks skipped); the suite also runs on GitHub's Windows runner.
- New end-to-end test against a fake Newznab indexer and a fake SABnzbd over real HTTP:
  - the first run searches the Skipped and the Wanted aired episodes, not the future or the ignored one, and sends both;
  - a failed download gets its release blocked, and a different release is sent in the same run;
  - a download stalled for 13 hours is blocked and replaced;
  - a second failure with "releases to try" set to 2 sets the episode aside;
  - Retry puts it back.
- Other new tests:
  - missing rules: not aired, no air date, Specials, paused show, file present, Archived, Skipped on and off;
  - search order;
  - settings validation and saving, with the interval surviving a restart;
  - the page and the menu link;
  - a run with no indexer or downloader skips the search and leaves episodes due;
  - the show-page "Not aired yet" label;
  - blocked releases rejected during search.
- Browser check in Chromium on a disposable copy: Autopilot page (turn on, save settings, run now, run history), show page labels (Missing for aired, Not aired yet for future); no page errors.
- Not performed: a run against your real indexers and download client.
