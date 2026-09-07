# TV Manager v17.13.1 - Windows EXE Build Script Safety Fix

This patch fixes the Windows EXE build workflow.

## Fixed

- `installer/windows/build-exe.ps1` no longer stages output inside `dist\TVManager` under the live application folder.
- Prevents recursive folder nesting such as `dist\TVManager\dist\TVManager\dist\TVManager`.
- Builds PyInstaller output in an external temporary folder.
- Publishes final Windows app output to `release\windows\TVManager`.
- Uses the project virtual environment Python instead of requiring a global `pyinstaller` command.
- Installs PyInstaller automatically when missing.
- Excludes runtime data, secrets, logs, backups, imports, release folders, build folders, and database files from the staged payload.

## Operator cleanup after a failed previous build

Before rerunning the fixed script, clean the recursive output:

```powershell
cd "C:\Acuityware TV Manager"
Remove-Item .\dist -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item .\build -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item .\release -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item .\TVManager.spec -Force -ErrorAction SilentlyContinue
.\installer\windows\build-exe.ps1
```
