# TV Manager Server Installation — SickChill Replacement

This guide is the full server-side runbook for installing TV Manager on the same server currently running SickChill and gradually replacing SickChill without losing your library, configuration notes, or downloaded/indexed files.

TV Manager is designed to be **local-first**. The safest replacement method is: install TV Manager beside SickChill, import a copy of SickChill's database, verify the library, then disable SickChill only after TV Manager is proven.

## 1. Replacement strategy

Use this order:

1. Back up SickChill.
2. Install TV Manager into a separate directory.
3. Start TV Manager on a test port or localhost only.
4. Import a **copy** of SickChill's `sickbeard.db`.
5. Validate shows, episodes, paths, missing files, duplicates, and metadata IDs.
6. Configure download clients, providers, naming, post-processing, and media server refresh.
7. Run both systems briefly with SickChill automation paused.
8. Disable SickChill.
9. Move TV Manager onto the desired production port / reverse proxy.
10. Keep rollback backups until the replacement is stable.

Do not point TV Manager at SickChill's live database file. Always copy the database first.

## 2. Before you start

Record the current SickChill details:

- SickChill install directory.
- SickChill data/config directory.
- SickChill database path, usually named `sickbeard.db`.
- SickChill web port.
- Media root paths.
- Download client settings.
- Post-processing folder.
- TV naming format.
- API key, if integrations use it.
- Service name: `sickchill`, `sickrage`, `sickbeard`, or similar.

Useful Linux discovery commands:

```bash
systemctl list-units --type=service | grep -Ei 'sick|tv|media'
ps aux | grep -Ei 'sickchill|sickrage|sickbeard' | grep -v grep
find / -name sickbeard.db 2>/dev/null
find / -iname 'config.ini' 2>/dev/null | grep -Ei 'sick|tv'
```

## 3. Back up SickChill

Stop SickChill briefly or pause automation before copying the database.

```bash
sudo systemctl stop sickchill || true
sudo systemctl stop sickrage || true
sudo systemctl stop sickbeard || true
```

Create a backup directory:

```bash
sudo mkdir -p /opt/tvmanager-migration-backups
sudo cp -a /path/to/sickbeard.db /opt/tvmanager-migration-backups/sickbeard.db.$(date +%Y%m%d-%H%M%S)
sudo cp -a /path/to/config.ini /opt/tvmanager-migration-backups/config.ini.$(date +%Y%m%d-%H%M%S) 2>/dev/null || true
```

Restart SickChill if you are not ready to cut over yet:

```bash
sudo systemctl start sickchill || true
sudo systemctl start sickrage || true
sudo systemctl start sickbeard || true
```

## 4. Install TV Manager on Linux

Recommended install path:

```text
/opt/tvmanager
```

Copy or unzip the TV Manager package onto the server:

```bash
sudo mkdir -p /opt/tvmanager
sudo unzip imdb-tv-manager-v17.2.0.zip -d /tmp/tvmanager-install
sudo rsync -a /tmp/tvmanager-install/tvmanager-v17.2.0/ /opt/tvmanager/
```

Install Python and venv support.

Debian/Ubuntu:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git unzip rsync
```

RHEL/Rocky/Alma:

```bash
sudo dnf install -y python3 python3-pip git unzip rsync
```

Create the service account and install the service:

```bash
cd /opt/tvmanager
sudo TVMANAGER_PORT=5050 TVMANAGER_HOST=127.0.0.1 bash scripts/install-linux-service.sh /opt/tvmanager
```

Check the service:

```bash
sudo systemctl status tvmanager --no-pager
sudo journalctl -u tvmanager -n 100 --no-pager
```

Test locally from the server:

```bash
curl http://127.0.0.1:5050/api/version
curl http://127.0.0.1:5050/routes
```

## 5. Run preflight checks

Before importing, run the read-only preflight checker:

```bash
cd /opt/tvmanager
sudo -u tvmanager .venv/bin/python server_preflight.py \
  --sickchill-db /opt/tvmanager-migration-backups/sickbeard.db.YYYYMMDD-HHMMSS \
  --tvmanager-db /opt/tvmanager/tvmanager.db \
  --media-root /path/to/TV \
  --host 127.0.0.1 \
  --port 5050
```

The report is written to:

```text
/opt/tvmanager/diagnostics/server-preflight.json
```

Resolve warnings before cutover, especially missing media roots, unavailable database files, or port conflicts.

## 6. Import SickChill data

Open TV Manager:

```text
http://127.0.0.1:5050/import
```

Use the Import Center in this order:

1. Select the copied SickChill database.
2. Click **Analyze**.
3. Review tables, show count, episode count, warnings, and path samples.
4. Click **Preview**.
5. Confirm skipped items, duplicate candidates, missing IDs, and path mappings.
6. Click **Import** only after preview looks correct.
7. Open **Library Health** after import.

Command-line/API flow, if needed:

```bash
curl -X POST http://127.0.0.1:5050/api/import/sickchill/analyze \
  -H 'Content-Type: application/json' \
  -d '{"path":"/opt/tvmanager-migration-backups/sickbeard.db.YYYYMMDD-HHMMSS"}'

curl -X POST http://127.0.0.1:5050/api/import/sickchill/preview \
  -H 'Content-Type: application/json' \
  -d '{"path":"/opt/tvmanager-migration-backups/sickbeard.db.YYYYMMDD-HHMMSS"}'
```

## 7. Validate the replacement

Open these pages:

```text
/routes
/about
/system
/library-health
/manager
/import
/settings
/postprocess
/operations
```

Minimum validation checklist:

- Version page shows the expected TV Manager version.
- Routes page lists `/about`, `/library-health`, and `/api/library/health-report`.
- Imported show count looks correct.
- Imported episode count looks correct.
- Library Health has no unexpected missing root paths.
- Sample show pages contain seasons and episode records.
- Existing downloaded files show as downloaded/available.
- Duplicate cleanup is only previewed, not automatically applied.
- Post-processing simulation mode is correct before automation is enabled.
- Download client connection tests pass.
- Media server refresh test passes, if configured.

## 8. Configure production access

Keep TV Manager bound to localhost when using a reverse proxy:

```env
HOST=127.0.0.1
PORT=5050
TVMANAGER_THREADS=8
TVMANAGER_HTTPS=0
```

For LAN access without a reverse proxy, enable browser authentication first in TV Manager, then bind to a LAN address. TV Manager intentionally refuses non-loopback production binding unless browser authentication is configured and enabled.

## 9. Caddy reverse proxy example

```caddyfile
tvmanager.example.com {
    reverse_proxy 127.0.0.1:5050
    encode gzip
}
```

Reload Caddy:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## 10. Nginx reverse proxy example

```nginx
server {
    listen 80;
    server_name tvmanager.example.com;

    location / {
        proxy_pass http://127.0.0.1:5050;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 11. Cutover from SickChill

When TV Manager is validated:

```bash
sudo systemctl stop sickchill || true
sudo systemctl disable sickchill || true
sudo systemctl stop sickrage || true
sudo systemctl disable sickrage || true
sudo systemctl stop sickbeard || true
sudo systemctl disable sickbeard || true
sudo systemctl restart tvmanager
```

Do not delete SickChill yet. Keep it installed but disabled until TV Manager has run successfully through several scheduler cycles.

## 12. Rollback plan

Rollback is simple if you have not deleted SickChill:

```bash
sudo systemctl stop tvmanager
sudo systemctl start sickchill || sudo systemctl start sickrage || sudo systemctl start sickbeard
```

Restore SickChill database if needed:

```bash
sudo cp -a /opt/tvmanager-migration-backups/sickbeard.db.YYYYMMDD-HHMMSS /path/to/sickbeard.db
sudo systemctl restart sickchill
```

TV Manager does not modify the copied SickChill database during analyze or preview.

## 13. Updates after initial install

For a new TV Manager package:

```bash
sudo systemctl stop tvmanager
sudo cp -a /opt/tvmanager/tvmanager.db /opt/tvmanager/backups/tvmanager.db.$(date +%Y%m%d-%H%M%S)
sudo unzip imdb-tv-manager-vNEXT.zip -d /tmp/tvmanager-update
sudo rsync -a --exclude tvmanager.db --exclude .env --exclude .venv --exclude diagnostics --exclude logs --exclude backups --exclude managed_trash /tmp/tvmanager-update/tvmanager-vNEXT/ /opt/tvmanager/
sudo chown -R tvmanager:tvmanager /opt/tvmanager
sudo -u tvmanager /opt/tvmanager/.venv/bin/pip install -r /opt/tvmanager/requirements.txt
sudo systemctl start tvmanager
sudo journalctl -u tvmanager -n 100 --no-pager
```

## 14. Server hardening checklist

- Use a dedicated `tvmanager` OS account.
- Keep the app behind Caddy/Nginx for remote access.
- Enable browser authentication before LAN/remote exposure.
- Use HTTPS at the reverse proxy.
- Do not commit or share `.env`, `tvmanager.db`, backups, diagnostics, API tokens, logs, or imported SickChill databases.
- Back up `tvmanager.db` before every update.
- Keep `managed_trash` until duplicate cleanup has been reviewed.

## 15. Final acceptance checklist

TV Manager can fully replace SickChill when:

- SickChill import completed without unexpected skipped shows.
- Library Health has been reviewed.
- Downloading/search/post-processing behavior has been tested in simulation first.
- Scheduler jobs are enabled intentionally.
- Backups are confirmed.
- `/system`, `/routes`, `/about`, and `/library-health` work from the production access path.
- SickChill is stopped and disabled, not deleted.
