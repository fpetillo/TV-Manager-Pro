# TV Manager v18.33.0 — update-server.ps1 installs the latest release

Built on v18.32.0.

## What changed

- `update-server.ps1` with no `-Version` now finds the newest `vX.Y.Z` release tag on GitHub (the same rule the automatic updater uses) and installs it. Before, each copy of the script was pinned to the release it shipped with, so an older copy kept reinstalling its own version.
- When the newest release is already installed, it says so and stops before taking a backup.
- `-Version 18.x.y` still installs a specific release; `-ArchivePath` (offline ZIP) requires `-Version`.

## Updating to this release

The copy of `update-server.ps1` on a server older than 18.33.0 is pinned to its own version, so name the version once:

```
.\update-server.ps1 -Version 18.33.0
```

From then on, `.\update-server.ps1` installs the latest release.

## Validation

- Tests: default is latest, not pinned; newest semver tag chosen across tags (ignores non-release tags); up to date stops before any backup.
