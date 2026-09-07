# Project delivery rules

- Every delivered code iteration must increment VERSION, update RELEASE_MANIFEST.json and CHANGELOG.md, and add matching docs/RELEASE_NOTES_v<version>.md.
- Run relevant checks and report failures accurately. Never carry forward stale passing-test claims.
- Commit and push authorized source changes to the existing GitHub branch; create/push the matching version tag. Do not include databases, secrets, imports, runtime logs, recovery folders or generated binaries.
- Distinguish source publication from activation in the running app. Verify UI actions in the browser when changing workflows.
- Do not stop unrelated processes or delete runtime data to prepare a release.
- Follow the user's knowledge-vault closeout requirement: update the project note and maintenance changelog in C:\Users\frank\Documents\Acuityware_Obsidian_Vault, commit, pull --rebase, push, and report the commit SHA. The user authorized direct closeout steps while project-closeout skill is unavailable.
