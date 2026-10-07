"""Unattended deployment of new TV Manager releases on a Windows source installation.

Run by the "TV Manager Auto Update" scheduled task (see install-auto-deploy.ps1) with
the base Python interpreter, never the installation's .venv, so the environment can be
replaced. Standard library only.

One run:
  1. Find the newest vX.Y.Z tag on GitHub; stop here if it is not newer than VERSION.
  2. Wait (bounded) until TV Manager reports no active jobs.
  3. Set the maintenance flag so the startup task cannot restart the old version,
     then request a graceful stop (server.py --stop-service drains active work).
  4. Run update-server.ps1, which verifies the release, takes a full recovery backup,
     installs dependencies and source, and rolls itself back on failure.
  5. Clear the flag, start the startup task and confirm /api/version reports the new
     version. If it does not, stop it, restore source, .venv and database from the
     recovery backup, and start the previous version again.

Every run writes .runtime/auto-update-status.json and appends to logs/auto-update.log.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

DEFAULTS = {
    "enabled": True,
    "repository": "fpetillo/TV-Manager-Pro",
    "production_task": "TV Manager Production",
    "max_wait_minutes": 120,
    "busy_poll_minutes": 5,
    "stop_timeout_seconds": 240,
    "start_timeout_seconds": 1500,  # snapshot + database check (10 min limit each) + server start
    "keep_backups": 5,
}
VERSION_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
LOCK_STALE_SECONDS = 6 * 3600
LOG_LIMIT = 2 * 1024 * 1024


def version_tuple(value):
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", str(value).strip())
    if not match:
        raise ValueError(f"Not a release version: {value!r}")
    return tuple(int(part) for part in match.groups())


def newest_tag(names):
    """Highest vX.Y.Z tag name, compared numerically (18.10.0 > 18.9.0)."""
    versions = [tuple(int(p) for p in m.groups()) for m in (VERSION_TAG.match(n or "") for n in names) if m]
    return ".".join(map(str, max(versions))) if versions else None


def long_path(path):
    path = Path(path)
    if os.name == "nt":
        text = str(path.absolute())
        if not text.startswith("\\\\?\\"):
            text = "\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text
        return Path(text)
    return path


class Environment:
    """Real side effects. Tests replace this with a fake."""

    def __init__(self, root):
        self.root = Path(root)

    def run(self, command, timeout):
        try:
            done = subprocess.run(command, cwd=str(self.root), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout)
            return done.returncode, (done.stdout or "") + (done.stderr or "")
        except subprocess.TimeoutExpired as exc:
            return 124, f"Timed out after {timeout}s: {exc}"
        except OSError as exc:
            return 127, str(exc)

    def http_json(self, url, headers=None, timeout=15):
        request = urllib.request.Request(url, headers={"User-Agent": "TV-Manager-Auto-Update", **(headers or {})})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, json.loads(response.read().decode("utf-8") or "null")
        except urllib.error.HTTPError as exc:
            return exc.code, None
        except (urllib.error.URLError, OSError, ValueError):
            return 0, None

    def sleep(self, seconds):
        time.sleep(seconds)

    def monotonic(self):
        return time.monotonic()

    def pid_alive(self, pid):
        if not pid:
            return False
        if os.name == "nt":
            import ctypes
            kernel = ctypes.windll.kernel32
            handle = kernel.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            try:
                code = ctypes.c_ulong()
                return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
            finally:
                kernel.CloseHandle(handle)
        try:
            os.kill(int(pid), 0)
            return True
        except OSError:
            return False

    def kill_tree(self, pid):
        if os.name == "nt":
            return self.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"], 60)
        try:
            os.kill(int(pid), 9)
            return 0, ""
        except OSError as exc:
            return 1, str(exc)

    def start_task(self, name):
        return self.run(["schtasks", "/Run", "/TN", name], 60)

    def run_updater(self, version):
        script = self.root / "update-server.ps1"
        return self.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                         "-InstallDir", str(self.root), "-Version", version], 3600)

    def venv_python(self):
        return str(self.root / ".venv" / "Scripts" / "python.exe") if os.name == "nt" else str(self.root / ".venv" / "bin" / "python")


class AutoUpdater:
    def __init__(self, root, env=None, log=None):
        self.root = Path(root).absolute()
        self.env = env or Environment(self.root)
        self.runtime = self.root / ".runtime"
        self.config = self.load_config()
        self._log = log
        self.backup = None

    # ------------------------------------------------------------------ plumbing
    def load_config(self):
        config = dict(DEFAULTS)
        path = self.root / "auto_update.json"
        if path.is_file():
            try:
                config.update(json.loads(path.read_text(encoding="utf-8-sig")))
            except ValueError as exc:
                raise ValueError(f"auto_update.json is not valid JSON: {exc}") from None
        return config

    def log(self, message):
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{stamp}  {message}"
        if self._log is not None:
            self._log.append(line)
        print(line, flush=True)
        folder = self.root / "logs"
        try:
            folder.mkdir(exist_ok=True)
            path = folder / "auto-update.log"
            if path.exists() and path.stat().st_size > LOG_LIMIT:
                os.replace(path, folder / "auto-update.log.1")
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass

    def write_status(self, result, **details):
        self.runtime.mkdir(exist_ok=True)
        record = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "result": result,
                  "installed_version": self.installed_version(), **details}
        if self.backup:
            record["recovery_backup"] = str(self.backup)
        temporary = self.runtime / "auto-update-status.json.tmp"
        temporary.write_text(json.dumps(record, indent=2), encoding="utf-8")
        os.replace(temporary, self.runtime / "auto-update-status.json")
        return record

    def installed_version(self):
        try:
            return (self.root / "VERSION").read_text(encoding="utf-8-sig").strip()
        except OSError:
            return ""

    def acquire_lock(self):
        self.runtime.mkdir(exist_ok=True)
        path = self.runtime / "auto-update.lock"
        try:
            if time.time() - path.stat().st_mtime > LOCK_STALE_SECONDS:
                path.unlink()
        except OSError:
            pass
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return None
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
        return path

    def set_maintenance(self, on, reason=""):
        flag = self.runtime / "maintenance.json"
        if on:
            self.runtime.mkdir(exist_ok=True)
            flag.write_text(json.dumps({"reason": reason, "since": time.time()}), encoding="utf-8")
        else:
            flag.unlink(missing_ok=True)

    # ------------------------------------------------------------------ discovery
    def latest_release(self):
        repo = self.config["repository"]
        names = []
        for page in range(1, 11):
            status, data = self.env.http_json(f"https://api.github.com/repos/{repo}/tags?per_page=100&page={page}",
                                              {"Accept": "application/vnd.github+json"}, 30)
            if status != 200 or not isinstance(data, list):
                if page == 1:
                    raise RuntimeError(f"Could not read release tags from GitHub (HTTP {status or 'no response'}).")
                break
            names += [str(item.get("name", "")) for item in data if isinstance(item, dict)]
            if len(data) < 100:
                break
        return newest_tag(names)

    def service_state(self):
        try:
            return json.loads((self.runtime / "service.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def base_url(self, state):
        host = str(state.get("host") or "127.0.0.1")
        if host in ("0.0.0.0", "::", ""):
            host = "127.0.0.1"
        if ":" in host:
            host = f"[{host}]"
        return f"http://{host}:{int(state.get('port') or 5050)}"

    def running(self):
        state = self.service_state()
        return state if state and self.env.pid_alive(state.get("pid")) else {}

    def version_answered(self, state):
        status, data = self.env.http_json(self.base_url(state) + "/api/version", timeout=10)
        return (data or {}).get("version") if status == 200 and isinstance(data, dict) else None

    # ------------------------------------------------------------------ idle wait
    def wait_until_idle(self, state):
        token = secrets.token_hex(32)
        token_path = self.runtime / "maintenance.token"
        token_path.write_text(token, encoding="utf-8")
        try:
            deadline = self.env.monotonic() + float(self.config["max_wait_minutes"]) * 60
            while True:
                status, data = self.env.http_json(self.base_url(state) + "/api/maintenance/activity",
                                                  {"X-TVManager-Maintenance": token}, 15)
                if status != 200 or not isinstance(data, dict):
                    self.log("Activity check unavailable on the running version; relying on the graceful stop to finish active work.")
                    return True
                busy = int(data.get("active_jobs") or 0) + int(data.get("busy_workers") or 0)
                if not busy:
                    return True
                kinds = ", ".join(data.get("active_kinds") or []) or "background work"
                if self.env.monotonic() >= deadline:
                    self.log(f"Still busy ({kinds}) after {self.config['max_wait_minutes']} minutes; deferring to the next run.")
                    return False
                self.log(f"Waiting for {busy} active job(s) to finish: {kinds}.")
                self.env.sleep(float(self.config["busy_poll_minutes"]) * 60)
        finally:
            token_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------ stop / start
    def stop(self, force_after_timeout=False):
        state = self.running()
        if not state:
            return True
        self.log(f"Requesting graceful stop of process {state.get('pid')} (active work drains first).")
        code, output = self.env.run([self.env.venv_python(), str(self.root / "server.py"), "--stop-service"], 120)
        if code != 0:
            self.log("Stop request failed: " + output.strip()[-500:])
        deadline = self.env.monotonic() + float(self.config["stop_timeout_seconds"])
        while self.env.pid_alive(state.get("pid")):
            if self.env.monotonic() >= deadline:
                if not force_after_timeout:
                    self.log("TV Manager did not stop within the timeout.")
                    return False
                self.log("TV Manager did not stop within the timeout; ending the process so recovery can continue.")
                self.env.kill_tree(state.get("pid"))
                self.env.sleep(5)
                return not self.env.pid_alive(state.get("pid"))
            self.env.sleep(3)
        self.log("TV Manager stopped.")
        return True

    def start_and_verify(self, expected):
        self.set_maintenance(False)
        code, output = self.env.start_task(self.config["production_task"])
        if code != 0:
            self.log(f"Could not start scheduled task '{self.config['production_task']}': " + output.strip()[-300:])
            return False
        deadline = self.env.monotonic() + float(self.config["start_timeout_seconds"])
        while self.env.monotonic() < deadline:
            state = self.running()
            if state:
                version = self.version_answered(state)
                if version == expected:
                    self.log(f"TV Manager {expected} is running and answering on {self.base_url(state)}.")
                    return True
            self.env.sleep(5)
        self.log(f"TV Manager {expected} did not answer within {self.config['start_timeout_seconds']} seconds.")
        return False

    # ------------------------------------------------------------------ recovery
    def restore_from_backup(self, backup):
        backup = Path(backup)
        record = json.loads((backup / "update.json").read_text(encoding="utf-8"))
        if Path(record.get("installation", "")).absolute() != self.root:
            raise ValueError("Recovery backup belongs to a different installation.")
        snapshot = backup / "installation"
        failed = backup / "failed-start"
        failed.mkdir(exist_ok=True)

        def set_aside(path, relative):
            target = failed / relative
            long_path(target.parent).mkdir(parents=True, exist_ok=True)
            shutil.move(str(long_path(path)), str(long_path(target)))

        for relative in record.get("release_files", []):
            destination = self.root / relative
            original = snapshot / relative
            if long_path(original).is_file():
                long_path(destination.parent).mkdir(parents=True, exist_ok=True)
                shutil.copy2(long_path(original), long_path(destination))
            elif long_path(destination).exists():
                set_aside(destination, relative)
        if long_path(snapshot / ".venv").is_dir():
            if long_path(self.root / ".venv").exists():
                set_aside(self.root / ".venv", ".venv")
            shutil.copytree(long_path(snapshot / ".venv"), long_path(self.root / ".venv"))
        if long_path(snapshot / "tvmanager.db").is_file():
            # The new version may have migrated the database during its failed start.
            for name in ("tvmanager.db", "tvmanager.db-wal", "tvmanager.db-shm"):
                if long_path(self.root / name).exists():
                    set_aside(self.root / name, name)
            for name in ("tvmanager.db", "tvmanager.db-wal", "tvmanager.db-shm"):
                if long_path(snapshot / name).is_file():
                    shutil.copy2(long_path(snapshot / name), long_path(self.root / name))
        record["status"] = "restored_after_failed_start"
        (backup / "update.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        return record.get("from_version")

    def prune_backups(self):
        keep = int(self.config.get("keep_backups") or 0)
        parent = self.root.parent / (self.root.name + " Update Backups")
        if keep <= 0 or not parent.is_dir():
            return
        finished = []
        for folder in parent.iterdir():
            try:
                status = json.loads((folder / "update.json").read_text(encoding="utf-8")).get("status")
            except (OSError, ValueError):
                continue
            if status == "installed_restart_required":
                finished.append(folder)
        for folder in sorted(finished, key=lambda p: p.name)[:-keep]:
            if self.backup and folder.resolve() == Path(self.backup).resolve():
                continue
            self.log(f"Removing old recovery backup {folder.name} (keeping the newest {keep}).")
            shutil.rmtree(long_path(folder), ignore_errors=True)

    # ------------------------------------------------------------------ main flow
    def run(self, check_only=False, target=None):
        lock = None if check_only else self.acquire_lock()
        if not check_only and lock is None:
            self.log("Another auto-update run is in progress; exiting.")
            return 0
        try:
            return self._run(check_only, target)
        except Exception as exc:  # report every unexpected failure in the status file
            self.log(f"Auto-update stopped with an error: {exc}")
            if not check_only:
                self.write_status("error", message=str(exc))
            return 1
        finally:
            if lock is not None:
                lock.unlink(missing_ok=True)

    def _run(self, check_only, target):
        current = self.installed_version()
        if not self.config.get("enabled", True) and not check_only:
            self.log("Auto-update is disabled in auto_update.json.")
            self.write_status("disabled")
            return 0
        if (self.root / "TVManagerService.exe").exists():
            message = "This is a packaged service installation; source auto-update does not apply."
            self.log(message)
            if not check_only:
                self.write_status("unsupported", message=message)
            return 1
        latest = target or self.latest_release()
        if not latest:
            raise RuntimeError("No vX.Y.Z release tags were found on GitHub.")
        if version_tuple(latest) <= version_tuple(current):
            self.log(f"Installed {current}; newest release {latest}. Nothing to do.")
            if not check_only:
                self.write_status("up_to_date", latest_version=latest)
            return 0
        if check_only:
            self.log(f"Installed {current}; newest release {latest}. An update would be installed.")
            return 0

        self.log(f"Updating TV Manager {current} -> {latest}.")
        state = self.running()
        if state and not self.wait_until_idle(state):
            self.write_status("deferred_busy", latest_version=latest, message="Active jobs did not finish in the waiting window.")
            return 0

        self.set_maintenance(True, f"auto-update to {latest}")
        try:
            if not self.stop():
                # No files changed yet. End the stuck process and bring the current version back.
                self.stop(force_after_timeout=True)
                started = self.start_and_verify(current)
                self.write_status("stop_timeout", latest_version=latest, restarted_previous=started,
                                  message="TV Manager did not stop in time. No files were changed; update will retry next run.")
                return 1
            code, output = self.env.run_updater(latest)
            for line in output.splitlines():
                if line.strip():
                    self.log("  updater: " + line.strip())
                found = re.search(r"Recovery backup:\s*(.+)$", line.strip())
                if found:
                    self.backup = found.group(1).strip()
            if code != 0:
                self.log("The updater reported a failure and restored the previous version itself. Restarting it.")
                started = self.start_and_verify(current)
                self.write_status("update_failed", latest_version=latest, restarted_previous=started,
                                  message="Update failed before activation; see logs/auto-update.log.")
                return 1
            if self.start_and_verify(latest):
                self.prune_backups()
                self.write_status("updated", previous_version=current, latest_version=latest)
                return 0

            self.log("New version failed to start. Restoring the previous version from the recovery backup.")
            self.set_maintenance(True, "rollback after failed start")
            self.stop(force_after_timeout=True)
            if not self.backup:
                self.write_status("failed_start_manual_recovery", latest_version=latest,
                                  message="New version did not start and no recovery backup path was reported.")
                return 1
            previous = self.restore_from_backup(self.backup)
            started = self.start_and_verify(previous)
            self.write_status("rolled_back" if started else "rollback_failed_start", previous_version=current,
                              latest_version=latest, restarted_previous=started,
                              message=f"{latest} failed to start; restored {previous}.")
            return 1
        finally:
            self.set_maintenance(False)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install new TV Manager releases unattended.")
    parser.add_argument("--install-dir", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--check", action="store_true", help="Report what would happen without changing anything.")
    parser.add_argument("--version", help="Install this release instead of the newest tag.")
    args = parser.parse_args(argv)
    if args.version:
        version_tuple(args.version)
    return AutoUpdater(args.install_dir).run(check_only=args.check, target=args.version)


if __name__ == "__main__":
    raise SystemExit(main())
