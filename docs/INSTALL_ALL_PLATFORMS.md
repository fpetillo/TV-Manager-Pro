# TV Manager Installation Guide — All Popular Platforms

This guide describes how to install TV Manager as a full SickChill replacement on common platforms.

## Before You Begin

Back up SickChill before any migration. Copy the SickChill database, configuration, and application folder to a safe location. Never import directly from the live SickChill database; copy `sickbeard.db` first.

## Windows 10/11

1. Install Python 3.12 or newer.
2. Extract the TV Manager release zip.
3. Copy the contents of the versioned folder into `C:\Acuityware TV Manager`.
4. Open PowerShell in that folder.
5. Run `setup.ps1`.
6. Run `run.ps1`.
7. Open `http://127.0.0.1:5050/launchpad`.

For production Windows deployments, use the Windows EXE installer build workflow in `docs/WINDOWS_EXE_INSTALLER.md`.

## Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git unzip
sudo mkdir -p /opt/tvmanager
sudo unzip imdb-tv-manager-v17.7.0.zip -d /tmp/tvmanager
sudo rsync -a --delete --exclude tvmanager.db /tmp/tvmanager/tvmanager-v17.7.0/ /opt/tvmanager/
cd /opt/tvmanager
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python server_preflight.py
python app.py
```

Then open `http://SERVER-IP:5050/launchpad` after configuring firewall and host settings.

## RHEL / Rocky / AlmaLinux

```bash
sudo dnf install -y python3 python3-pip git unzip rsync
sudo mkdir -p /opt/tvmanager
sudo unzip imdb-tv-manager-v17.7.0.zip -d /tmp/tvmanager
sudo rsync -a --delete --exclude tvmanager.db /tmp/tvmanager/tvmanager-v17.7.0/ /opt/tvmanager/
cd /opt/tvmanager
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python server_preflight.py
```

Use `scripts/install-linux-service.sh` to create a systemd service.

## macOS

```bash
brew install python git
unzip imdb-tv-manager-v17.7.0.zip
cd tvmanager-v17.7.0
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5050/launchpad`.

## Docker / Container Hosts

A first-class Docker image is planned. Until then, use a minimal Python container with a persistent volume for `tvmanager.db`, imports, backups, diagnostics, and logs. Do not bake runtime data into the image.

## NAS / Media Servers

Use a Linux install when the NAS supports Python 3.12+ and persistent service management. Mount media roots read/write only after testing with Library Health.

## Replacing SickChill

1. Install TV Manager side-by-side.
2. Copy SickChill `sickbeard.db` into TV Manager `imports/`.
3. Analyze import.
4. Preview import.
5. Run import with progress visible.
6. Open Library Health.
7. Resolve path and duplicate findings.
8. Disable SickChill automation.
9. Enable TV Manager automation.
10. Keep SickChill backup until TV Manager has run successfully for several days.
