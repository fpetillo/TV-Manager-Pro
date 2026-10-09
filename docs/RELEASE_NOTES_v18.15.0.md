# TV Manager v18.15.0 — Post Processing "Replace anyway"

Built on v18.14.1.

## What changed

Post Processing blocks a file when the library already has that episode and the new file is not an upgrade. The preview shows reasons such as **Replacement is not higher quality or a corrective release** or **Would downgrade quality**. That rule protects good files, but it also blocked the case where the existing file is wrong, for example a different show or episode saved under this episode's name, and the correct file is the same quality.

Blocked rows caused by the quality rule now have a **Replace anyway** checkbox in the preview:

- Tick it on each file that should replace what is in the library. The row is outlined and the selection summary counts it.
- **Confirm & Process Selected** and **Confirm & Process All Approved** both include ticked files. The confirmation dialog states how many files will replace an existing file even though they are not an upgrade.
- The existing file is moved to managed trash, never deleted, and the replacement is listed under **Upgrades**, where **Rollback** restores the original.
- A file already sitting at the final library path that the database no longer points at is also moved to managed trash instead of stopping the run with "Destination already exists".
- Each override is written to the event log as `replacement_override` with the reason that was overridden.

Nothing else changes. Automatic post-processing and files that are not ticked keep the safe upgrade rules. Rows blocked for other reasons, such as a missing library folder, have no override.

## API

`POST /api/postprocess/run/start` and `POST /api/postprocess/run` accept `force_replace_sources`: a list of source paths, from the preview, that may replace an existing file regardless of quality. Each must also be in `selected_sources`.

## Validation

- 546 passed, 11 skipped (Windows-only PowerShell, updater lease and service checks on the Linux build host).
- New tests run a real TV Manager copy: same-quality replacement still blocked without the override; with it, the correct file replaces the wrong one, the wrong one is in managed trash and the replacement record is Completed.
- Browser check on a disposable copy: preview shows Replace anyway on the blocked row only; ticking it updates the summary; the confirmation states the override; processing replaced the file and imported a second, normal episode in the same run; no page errors.
- 181 Python files parse; 43 JavaScript files pass `node --check`.
