# Post Processing Workflow

TV Manager post processing is designed to feel familiar to SickChill operators while adding safer preview/apply controls.

## Recommended operator flow

1. Open **Post Processing**.
2. Confirm the configured **Completed TV downloads** folder.
3. Optionally enter an **Override folder** for a one-time run.
4. Click **Preview Folder**.
5. Review matched files, destination paths, blocked upgrades, and unmatched files.
6. Select only the files you want to process or choose **Process All Approved**.
7. TV Manager applies naming, move/copy/hardlink behavior, associated-file handling, upgrade protection, and audit history.

## Folder selection

Web browsers cannot safely browse the server filesystem the same way a desktop app can. The operator enters the folder path as seen by the TV Manager server:

- Windows example: `D:\Downloads\TV`
- Linux example: `/downloads/tv`
- Docker example: `/downloads/tv`, mapped from the host volume

## Safety rules

- Preview does not move files.
- Blocked upgrades are not processed.
- Existing destination files are not silently overwritten.
- Existing library files are staged through managed replacement safeguards before replacement.
- Operators can use **Process Selected** for chosen preview rows instead of processing the entire folder.

## SickChill replacement guidance

Set the configured folder to the same completed TV download directory that SickChill used. Run preview first after migration and confirm naming/path output before enabling automatic workflows.
