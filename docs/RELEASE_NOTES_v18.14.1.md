# TV Manager v18.14.1 — Auto-deploy fixes found on the server

Built on v18.14.0.

## Fix

`install-auto-deploy.ps1` stopped with "TV Manager is running from this folder" even when TV Manager was stopped. Windows PowerShell 5.1 removes double quotes from arguments it passes to programs. The script's running check, `runtime_guard.acquire(".")`, therefore reached Python as `acquire(.)`, failed with a syntax error, and any failure was treated as "running".

The check now:

- uses Python code with no quotes (`acquire(os.getcwd())`);
- reports "running" only when TV Manager itself says it is already running;
- shows any other failure with its actual message.

## Startup under the scheduled task

On the server, the startup task stalled on the database check: `db_doctor.py` sat for over five minutes using no CPU, and its report file was never written. The same check run by hand finished in 16 seconds with `quick_check: ok`, so the database is healthy. The difference was that `start-production.ps1` captured the check's output through a PowerShell pipeline, which stalled in the task's windowless session.

`start-production.ps1` now:

- runs the snapshot and the database check as separate processes that write to `logs\protect_db.*.log` and `logs\db_doctor.*.log`, not through a pipeline;
- gives each step a 10-minute limit and stops a stuck step, including the real Python process under the `.venv` launcher, so the task retries instead of hanging;
- still blocks startup (`.runtime\startup-blocked.json`) when the check reports actual damage;
- logs how long each step took in `logs\startup.log`;
- clears Python caches only in TV Manager's own folders, no longer scanning `.venv`, backups or imports.

Startup can take several minutes before the server answers, so the auto-updater now waits up to 25 minutes (`start_timeout_seconds` 1500, was 300) before judging a new version as failed. Setup also waits up to 25 minutes and shows startup progress as it happens. **An existing `auto_update.json` keeps its old value; change `start_timeout_seconds` to 1500 there.**

## Validation

- Reproduced under PowerShell 7 with Windows PowerShell 5.1 argument passing (`$PSNativeCommandArgumentPassing = 'Legacy'`): the old check exited with SyntaxError; the new one reports "not running" when stopped and correctly detects a real running instance holding the lease.
- New tests reject double quotes inside any inline `-c '...'` Python command in the repository's PowerShell scripts, and check that the running message matches runtime_guard's wording.
- The new startup script was run with PowerShell against a stub installation in three cases. A normal start logged step timings and launched the server. A hung check was stopped at its limit, without blocking startup and with no process left behind. A failed check blocked startup with the reason recorded.
- pytest: 542 passed, 11 skipped (Windows-only checks on the Linux build host). All PowerShell scripts parse.

## Activation

On a server already at 18.14.0, replace `install-auto-deploy.ps1` with this version (or update with `update-server.ps1 -Version 18.14.1`), then run it as Administrator. Once installed, the nightly task updates the rest of the files to 18.14.1 automatically.
