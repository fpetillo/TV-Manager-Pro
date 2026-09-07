# Windows EXE Installer

TV Manager includes a Windows EXE packaging helper at:

```powershell
installer\windows\build-exe.ps1
```

## v17.13.3 safety notes

The build script is safe for install paths containing spaces, including:

```text
C:\Acuityware TV Manager
```

It invokes ROBOCOPY using a PowerShell argument array instead of `Start-Process -ArgumentList`, which prevents Windows paths with spaces from being split incorrectly.

## Build steps

From the TV Manager folder:

```powershell
cd "C:\Acuityware TV Manager"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\installer\windows\build-exe.ps1
```

The final payload is written to:

```text
release\windows\TVManager
```

The launcher is:

```text
release\windows\TVManager\TVManager.exe
```

## What is excluded

The build excludes local runtime data and secrets:

- `.env`
- `tvmanager.db`
- `imports`
- `logs`
- `diagnostics`
- `backups`
- `managed_trash`
- `.venv`
- `.git`
- `build`, `dist`, and `release`

Copy `.env` and `tvmanager.db` separately only when migrating an existing installation.

## Inno Setup

After the EXE payload is staged, compile:

```text
installer\windows\TVManager.iss
```

The Inno Setup script uses `release\windows\TVManager\*` as its source.
