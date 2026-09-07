#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/opt/tvmanager}"
APP_USER="${TVMANAGER_USER:-tvmanager}"
PORT="${TVMANAGER_PORT:-5050}"
HOST="${TVMANAGER_HOST:-127.0.0.1}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root or with sudo." >&2
  exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

id "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$APP_DIR" "$APP_DIR/imports" "$APP_DIR/backups" "$APP_DIR/diagnostics" "$APP_DIR/managed_trash"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

sudo -u "$APP_USER" "$PYTHON_BIN" -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [[ ! -f "$APP_DIR/.env" ]]; then
  cat > "$APP_DIR/.env" <<EOF
HOST=$HOST
PORT=$PORT
TVMANAGER_HTTPS=0
TVMANAGER_THREADS=8
EOF
  chown "$APP_USER":"$APP_USER" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
fi

cat > /etc/systemd/system/tvmanager.service <<EOF
[Unit]
Description=TV Manager
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=-$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/server.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable tvmanager.service
systemctl restart tvmanager.service
systemctl --no-pager status tvmanager.service
