# Contributing

1. Create a branch from the current default branch.
2. Preserve backward compatibility with existing `tvmanager.db` installations.
3. Never commit credentials, `.env`, imported SickChill secrets, runtime databases or diagnostic bundles.
4. Run `validate-release.ps1` before submitting changes.
5. Update `CHANGELOG.md`, `FEATURES.md` and relevant files under `docs/` for every user-visible feature.
