# TV Manager v17.13.3 - Windows EXE Robocopy Quoting Patch

This patch fixes the Windows EXE builder when TV Manager is installed under a path containing spaces, such as `C:\Acuityware TV Manager`.

## Fixed

- Replaced `Start-Process -ArgumentList` for ROBOCOPY staging with direct PowerShell argument-array invocation.
- Prevents ROBOCOPY from splitting `C:\Acuityware TV Manager` into `C:\Acuityware`, `TV`, and `Manager`.
- Keeps EXE staging outside the project tree under `%TEMP%\TVManagerBuild`.
- Keeps final output under `release\windows\TVManager`.
- Keeps runtime files, secrets, databases, imports, logs, diagnostics, backups, and previous build output excluded.
- Reduced ROBOCOPY retry/wait settings for faster operator feedback during packaging.

## Operator cleanup

If a previous build produced recursive `dist\TVManager\dist\TVManager` folders, stop the build and remove `dist`, `build`, and `release` once before rerunning this version.
