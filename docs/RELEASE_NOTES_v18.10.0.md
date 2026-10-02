# TV Manager v18.10.0 — Folder recovery, force download and reliable episode search

## Correct a missing show folder during metadata refresh

Refresh Metadata now opens a folder picker when the episode storage folder is undefined, missing or unavailable. Choose a configured library root and show folder, then use **Save Folder & Retry Metadata**. The selected show folder can be created immediately beneath an existing, accessible root. **More folder options** lets you add another library root without leaving the task. Current folder and free space remain visible; mapped server paths are respected.

Cancelling stops the refresh without changing the show's location. Saving does not move existing files. Updating recorded episode paths remains a separate unchecked option, intended only for files already moved. Unavailable roots/shares are never silently recreated. Metadata bulk results in Library Health and Manage Center list **Fix Folder & Refresh** links; background metadata can finish while reporting folders that need attention.

The early emergency Library Health route previously hid the interactive page. It now delegates to the full page when available and retains the fallback when it is not.

## Deliberately repeat a download

When sending an episode release reports an active download or an already processed release, choose **Force Download…**, review the existing episode/season-pack downloads, then **Confirm Force Download**. This is available in Show Detail, classic Shows and Download Center. Cancel sends nothing. The selected release is submitted again, while old downloads and history are kept; existing transfers are not cancelled.

Confirmation expires after five minutes and is bound to the release and reviewed download state. A successful submission makes that confirmation unusable again. Progress-only polling does not expire the review. A still-running or uncertain prior handoff must be resolved in Download Center first. Resolution, quality/rejection and failed-release restrictions remain enforced. The downloader can still reject or merge a duplicate, and existing post-processing replacement protections remain in effect.

## Episode Search fixes

Search buttons now handle titles such as **Wonka's The Golden Ticket** without inserting the title into executable HTML. Apostrophes previously broke the click handler before any request reached the server. Both Show Detail and classic Shows use bound handlers. Search windows now stay above the sidebar so navigation cannot intercept their buttons. Classic search displays request errors, and returning from a successful download keeps the confirmation visible after reloading episodes.

## Validation

- 437 tests passed; two existing Windows symbolic-link tests skipped because the account lacks permission.
- 67 top-level Python modules parsed; 41 JavaScript syntax checks passed; dependency consistency passed.
- Real isolated Flask tests cover folder checks/creation/retry, both metadata routes, all Library Health aliases, duplicate recovery, signed/tampered/replayed force reviews and CSRF.
- Acquisition tests verify retained history, active season-pack conflicts, stale review rejection, unresolved handoff protection, timeout recovery and current resolution/blacklist enforcement.
- Browser checks reproduced the apostrophe error, then verified searches in both show screens, sidebar layering, duplicate review/cancel/confirm, retained original download, missing/undefined folders, inline root addition and bulk repair links.
- Tests used a separate database, synthetic shows and a simulated downloader. No production metadata, media, settings or download client was changed. No new executable or Inno installer build is claimed. Full SickChill parity is not claimed.

## Update an existing source installation

Source: https://github.com/fpetillo/TV-Manager-Pro/tree/v18.10.0

ZIP: https://github.com/fpetillo/TV-Manager-Pro/archive/refs/tags/v18.10.0.zip

1. Stop TV Manager on the server and back up its installation/data folder while stopped.
2. Extract the tagged ZIP to a separate folder. Copy the **contents** of TV-Manager-Pro-18.10.0 into the existing application folder, replacing source files. Do not nest the extracted folder inside the installation or delete existing files to make it match GitHub.
3. Keep tvmanager.db and related data, .env, local settings, backups, job/recovery history and the server's working .venv. The GitHub source archive does not replace these runtime files. Do not copy a .venv from another computer.
4. In the existing application folder, use the working environment to install requirements and verify dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
Get-Content .\VERSION
```

5. Restart with the server's existing launcher/service. Refresh open browser pages (Ctrl+F5) and confirm v18.10.0 in the footer or About.

Source publication does not activate the update on 192.168.1.16. That server was not restarted or deployed to during this work. If the installation runs a packaged executable, replacing source alone does not update that executable; use the source launcher or a separately built package.
