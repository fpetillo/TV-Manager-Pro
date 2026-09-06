# Windows Deployment

For a complete new-PC installation, migration, upgrade, and troubleshooting procedure, see [Fresh Windows PC Installation](WINDOWS_FRESH_INSTALL.md).

## Compatible runner

`run.ps1` continues to start the Flask application the same way as previous releases. Use this while testing an upgrade.

## Production runner

Run `setup.ps1` once after upgrading so the v15 dependencies are installed. Then:

```powershell
.\run-prod.ps1
```

The production runner uses Waitress and starts the TV Manager scheduler.

Environment variables:
- `HOST` — defaults to `127.0.0.1`
- `PORT` — defaults to `5050`
- `TVMANAGER_THREADS` — defaults to `8`

## Start automatically at logon

```powershell
.\install-production-startup.ps1
```

This creates the `TV Manager Production` Scheduled Task with automatic restart behavior. It does not delete the existing `TV Manager` task; remove or disable the old task if switching permanently so only one web server instance is launched. Scheduler leases protect automation jobs if two instances are accidentally started, but running two web servers on the same port will still fail.

## Status

```powershell
.\status.ps1
```

The script queries `http://127.0.0.1:5050/api/health` by default.
