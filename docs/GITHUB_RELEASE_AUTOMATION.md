# GitHub Release Automation

`release-and-push.ps1` is the safe local release script for committing TV Manager source changes from Windows after a packaged update has been copied into `C:\Acuityware TV Manager`.

Run from PowerShell:

```powershell
cd "C:\Acuityware TV Manager"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\release-and-push.ps1 18.0.0
```

The script stops local Python processes, removes generated `dist`, `build`, `release`, cache and spec files, strengthens `.gitignore`, stages only source-safe files, commits, and pushes.

It intentionally excludes `.env`, `tvmanager.db`, database sidecar files, logs, diagnostics, backups, imports, managed trash, build output, and packaged installers.
