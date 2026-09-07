# Production Linux Deployment

This document is the generic production deployment guide for TV Manager on Linux. For replacing SickChill specifically, also read `docs/SICKCHILL_REPLACEMENT_SERVER_INSTALL.md`.

## Layout

Recommended layout:

```text
/opt/tvmanager              application and writable data
/opt/tvmanager/.venv        Python virtual environment
/opt/tvmanager/tvmanager.db SQLite database
/opt/tvmanager/imports      import staging
/opt/tvmanager/backups      app database backups
/opt/tvmanager/diagnostics  generated diagnostics
/opt/tvmanager/managed_trash safe cleanup destination
```

## Install

```bash
sudo mkdir -p /opt/tvmanager
sudo unzip imdb-tv-manager-v17.2.0.zip -d /tmp/tvmanager-install
sudo rsync -a /tmp/tvmanager-install/tvmanager-v17.2.0/ /opt/tvmanager/
cd /opt/tvmanager
sudo bash scripts/install-linux-service.sh /opt/tvmanager
```

## Service commands

```bash
sudo systemctl status tvmanager --no-pager
sudo systemctl restart tvmanager
sudo journalctl -u tvmanager -f
```

## Health checks

```bash
curl http://127.0.0.1:5050/api/version
curl http://127.0.0.1:5050/api/routes
curl http://127.0.0.1:5050/api/system/health
```

## Environment

Use `/opt/tvmanager/.env`:

```env
HOST=127.0.0.1
PORT=5050
TVMANAGER_THREADS=8
TVMANAGER_HTTPS=0
```

Keep `HOST=127.0.0.1` when TV Manager is behind a reverse proxy.
