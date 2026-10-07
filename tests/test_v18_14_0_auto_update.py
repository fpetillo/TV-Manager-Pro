"""v18.14.0: unattended deployment (auto_update.py) and the token-gated activity endpoint."""
import json
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest
from flask import Flask, jsonify, request

import auto_update

ROOT = Path(__file__).resolve().parents[1]


class FakeServer:
    """Simulates the startup task, the TV Manager process, GitHub and update-server.ps1."""

    def __init__(self, root, tags=("v18.13.0", "v18.14.0", "v18.9.0"), activity=None,
                 updater_ok=True, new_version_starts=True, stop_hangs=False):
        self.root = Path(root)
        self.tags = list(tags)
        self.activity = list(activity or [])
        self.updater_ok = updater_ok
        self.new_version_starts = new_version_starts
        self.stop_hangs = stop_hangs
        self.clock = 0.0
        self.pid = None
        self.next_pid = 100
        self.running_version = None
        self.stop_requested_at = None
        self.calls = []
        self.backup = None

    # process model -------------------------------------------------------
    def launch(self):
        version = (self.root / "VERSION").read_text().strip()
        if (self.root / ".runtime" / "maintenance.json").exists():
            return  # start-production.ps1 exits immediately during maintenance
        if version != "18.13.0" and not self.new_version_starts:
            return  # the new release crashes on start
        self.next_pid += 1
        self.pid = self.next_pid
        self.running_version = version
        (self.root / ".runtime").mkdir(exist_ok=True)
        (self.root / ".runtime" / "service.json").write_text(json.dumps({"pid": self.pid, "host": "0.0.0.0", "port": 5050}))

    def exit(self):
        self.pid = None
        self.running_version = None
        (self.root / ".runtime" / "service.json").unlink(missing_ok=True)

    # Environment interface -----------------------------------------------
    def sleep(self, seconds):
        self.clock += seconds
        if self.pid and self.stop_requested_at is not None and not self.stop_hangs and self.clock - self.stop_requested_at >= 6:
            self.exit()
            self.stop_requested_at = None

    def monotonic(self):
        return self.clock

    def pid_alive(self, pid):
        return bool(pid) and pid == self.pid

    def kill_tree(self, pid):
        self.calls.append(("kill", pid))
        if pid == self.pid:
            self.exit()
        return 0, ""

    def venv_python(self):
        return "python"

    def run(self, command, timeout):
        self.calls.append(("run", tuple(command[1:])))
        if "--stop-service" in command:
            self.stop_requested_at = self.clock
        return 0, ""

    def start_task(self, name):
        self.calls.append(("start_task", name))
        self.launch()
        return 0, ""

    def run_updater(self, version):
        self.calls.append(("updater", version))
        assert self.pid is None, "updater must only run once TV Manager has stopped"
        if not self.updater_ok:
            return 1, "UPDATE FAILED: dependency install failed"
        backup = self.root.parent / (self.root.name + " Update Backups") / ("20261007-030000-v18.13.0-abc")
        snapshot = backup / "installation"
        (snapshot / ".venv").mkdir(parents=True)
        (snapshot / ".venv" / "marker").write_text("old-venv")
        for name in ("app.py", "VERSION", "tvmanager.db"):
            (snapshot / name).write_bytes((self.root / name).read_bytes())
        (backup / "update.json").write_text(json.dumps({"installation": str(self.root.absolute()), "from_version": "18.13.0",
                                                        "to_version": version, "release_files": ["app.py", "VERSION", "new_module.py"],
                                                        "status": "installed_restart_required"}))
        (self.root / "app.py").write_text("new code")
        (self.root / "new_module.py").write_text("new")
        (self.root / "VERSION").write_text(version)
        (self.root / ".venv" / "marker").write_text("new-venv")
        (self.root / "tvmanager.db").write_text("migrated-by-new-version")
        (self.root / "tvmanager.db-wal").write_text("new-wal")
        self.backup = backup
        return 0, f"Creating verified recovery backup\nUpdated source to v{version}.\nRecovery backup: {backup}\n"

    def http_json(self, url, headers=None, timeout=15):
        self.calls.append(("http", url.split("?")[0]))
        if url.startswith("https://api.github.com/"):
            page = int(url.rsplit("page=", 1)[1])
            return 200, [{"name": t} for t in self.tags] if page == 1 else []
        if not self.pid:
            return 0, None
        if url.endswith("/api/version"):
            return 200, {"version": self.running_version}
        if url.endswith("/api/maintenance/activity"):
            token = (self.root / ".runtime" / "maintenance.token").read_text()
            assert headers["X-TVManager-Maintenance"] == token
            busy = self.activity.pop(0) if self.activity else 0
            return 200, {"active_jobs": busy, "busy_workers": 0, "active_kinds": ["show_folder_scan"] if busy else []}
        return 404, None


@pytest.fixture
def install(tmp_path):
    root = tmp_path / "Acuityware TV Manager"
    (root / ".venv").mkdir(parents=True)
    (root / ".venv" / "marker").write_text("old-venv")
    (root / "VERSION").write_text("18.13.0")
    (root / "app.py").write_text("old code")
    (root / "tvmanager.db").write_text("old-db")
    return root


def updater_for(root, server, **config):
    (root / "auto_update.json").write_text(json.dumps({"keep_backups": 0, **config}))
    return auto_update.AutoUpdater(root, env=server, log=[])


def status(root):
    return json.loads((root / ".runtime" / "auto-update-status.json").read_text())


def test_newest_tag_compares_numerically_and_ignores_other_tags():
    assert auto_update.newest_tag(["v18.9.0", "v18.10.0", "v18.13.0", "release-1", "v18.13.0-rc1", "v2.0"]) == "18.13.0"
    assert auto_update.newest_tag(["nothing"]) is None


def test_up_to_date_changes_nothing(install):
    server = FakeServer(install, tags=["v18.13.0"])
    server.launch()
    assert updater_for(install, server).run() == 0
    assert status(install)["result"] == "up_to_date"
    assert not any(c[0] in ("updater", "start_task") or "--stop-service" in str(c) for c in server.calls)
    assert server.running_version == "18.13.0"


def test_check_only_reports_without_touching_anything(install):
    server = FakeServer(install)
    server.launch()
    updater = updater_for(install, server)
    assert updater.run(check_only=True) == 0
    assert any("18.14.0. An update would be installed" in line for line in updater._log)
    assert not (install / ".runtime" / "auto-update-status.json").exists()
    assert [c for c in server.calls if c[0] != "http"] == []


def test_full_update_waits_for_jobs_stops_gracefully_updates_and_verifies(install):
    server = FakeServer(install, activity=[2, 1, 0])
    server.launch()
    updater = updater_for(install, server, busy_poll_minutes=1)
    assert updater.run() == 0
    record = status(install)
    assert record["result"] == "updated" and record["installed_version"] == "18.14.0" and record["previous_version"] == "18.13.0"
    assert server.running_version == "18.14.0"
    order = [c[0] if c[0] != "run" else "stop" for c in server.calls if c[0] != "http"]
    assert order == ["stop", "updater", "start_task"]
    assert sum("Waiting for" in line for line in updater._log) == 2
    assert not (install / ".runtime" / "maintenance.json").exists()
    assert not (install / ".runtime" / "maintenance.token").exists()
    assert not (install / ".runtime" / "auto-update.lock").exists()
    assert "Updating TV Manager 18.13.0 -> 18.14.0." in (install / "logs" / "auto-update.log").read_text()


def test_busy_past_the_window_defers_without_stopping(install):
    server = FakeServer(install, activity=[1] * 50)
    server.launch()
    assert updater_for(install, server, max_wait_minutes=10, busy_poll_minutes=5).run() == 0
    assert status(install)["result"] == "deferred_busy"
    assert server.running_version == "18.13.0"
    assert not any(c[0] == "updater" or "--stop-service" in str(c) for c in server.calls)


def test_updater_failure_restarts_the_previous_version(install):
    server = FakeServer(install, updater_ok=False)
    server.launch()
    assert updater_for(install, server).run() == 1
    record = status(install)
    assert record["result"] == "update_failed" and record["restarted_previous"] is True
    assert server.running_version == "18.13.0"


def test_failed_start_restores_source_venv_and_database(install):
    server = FakeServer(install, new_version_starts=False)
    server.launch()
    assert updater_for(install, server, start_timeout_seconds=30).run() == 1
    record = status(install)
    assert record["result"] == "rolled_back" and record["restarted_previous"] is True
    assert server.running_version == "18.13.0"
    assert (install / "VERSION").read_text() == "18.13.0" and (install / "app.py").read_text() == "old code"
    assert not (install / "new_module.py").exists()
    assert (install / ".venv" / "marker").read_text() == "old-venv"
    assert (install / "tvmanager.db").read_text() == "old-db" and not (install / "tvmanager.db-wal").exists()
    aside = server.backup / "failed-start"
    assert (aside / "tvmanager.db").read_text() == "migrated-by-new-version"
    assert (aside / "tvmanager.db-wal").exists() and (aside / "new_module.py").exists()
    assert json.loads((server.backup / "update.json").read_text())["status"] == "restored_after_failed_start"


def test_stop_timeout_changes_no_files_and_brings_current_version_back(install):
    server = FakeServer(install, stop_hangs=True)
    server.launch()
    assert updater_for(install, server, stop_timeout_seconds=30).run() == 1
    assert status(install)["result"] == "stop_timeout"
    assert not any(c[0] == "updater" for c in server.calls)
    assert any(c[0] == "kill" for c in server.calls)
    assert server.running_version == "18.13.0" and (install / "VERSION").read_text() == "18.13.0"


def test_not_running_still_updates_and_starts(install):
    server = FakeServer(install)
    assert updater_for(install, server).run() == 0
    assert status(install)["result"] == "updated" and server.running_version == "18.14.0"


def test_disabled_config_and_concurrent_runs_do_nothing(install):
    server = FakeServer(install)
    assert updater_for(install, server, enabled=False).run() == 0
    assert status(install)["result"] == "disabled" and server.calls == []
    (install / ".runtime" / "auto-update.lock").write_text("123")
    assert updater_for(install, server, enabled=True).run() == 0
    assert server.calls == []


def test_github_failure_is_reported(install):
    server = FakeServer(install)
    server.http_json = lambda *a, **k: (0, None)
    assert updater_for(install, server).run() == 1
    assert status(install)["result"] == "error" and "GitHub" in status(install)["message"]


def test_prune_keeps_newest_finished_backups(install):
    parent = install.parent / (install.name + " Update Backups")
    for stamp in ("20260101", "20260201", "20260301", "20260401"):
        folder = parent / f"{stamp}-v18.0.0-x"
        folder.mkdir(parents=True)
        (folder / "update.json").write_text(json.dumps({"status": "installed_restart_required"}))
    kept = parent / "20250101-v17.0.0-rolled"
    kept.mkdir()
    (kept / "update.json").write_text(json.dumps({"status": "rolled_back"}))
    updater = updater_for(install, FakeServer(install), keep_backups=2)
    updater.prune_backups()
    assert sorted(p.name for p in parent.iterdir()) == ["20250101-v17.0.0-rolled", "20260301-v18.0.0-x", "20260401-v18.0.0-x"]


# ---------------------------------------------------------------- activity endpoint

def activity_client(tmp_path, jobs):
    app = Flask(__name__)
    public = set()
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    ns = dict(app=app, request=request, jsonify=jsonify, os=__import__("os"), threading=threading, APP_VERSION="18.14.0",
              PUBLIC_PATHS=public, app_paths=SimpleNamespace(application_root=lambda: str(tmp_path)),
              job_center=SimpleNamespace(list_jobs=lambda limit=200: jobs, TERMINAL_STATUSES={"complete", "error", "cancelled"}))
    exec(source[source.index("MAINTENANCE_TOKEN_FILE="):source.index('@app.post("/api/jobs/<job_id>/cancel")')], ns)
    assert "/api/maintenance/activity" in public
    return app.test_client()


def test_activity_endpoint_requires_the_local_token(tmp_path):
    client = activity_client(tmp_path, [{"kind": "postprocess", "status": "running"}, {"kind": "x", "status": "complete"}])
    assert client.get("/api/maintenance/activity").status_code == 404  # no token file
    (tmp_path / ".runtime").mkdir()
    token = "a" * 64
    (tmp_path / ".runtime" / "maintenance.token").write_text(token)
    assert client.get("/api/maintenance/activity", headers={"X-TVManager-Maintenance": "wrong"}).status_code == 404
    data = client.get("/api/maintenance/activity", headers={"X-TVManager-Maintenance": token}).get_json()
    assert data["active_jobs"] == 1 and data["active_kinds"] == ["postprocess"] and data["version"] == "18.14.0"


# ---------------------------------------------------------------- Windows scripts

def test_windows_scripts_wire_the_maintenance_flag_and_graceful_mode():
    start = (ROOT / "start-production.ps1").read_text(encoding="utf-8")
    assert "maintenance.json" in start and "--service" in start and "db_doctor.py" in start and "protect_db.py" in start
    nightly = (ROOT / "auto-update.ps1").read_text(encoding="utf-8")
    assert "auto_update.py" in nightly and "_base_executable" in nightly
    setup = (ROOT / "install-auto-deploy.ps1").read_text(encoding="utf-8")
    for needle in ("TV Manager Production", "TV Manager Auto Update", "-AtStartup", "start-production.ps1", "auto-update.ps1", "Get-Credential"):
        assert needle in setup
    assert ".runtime/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def _param_block(text):
    """The script's top-level param( ... ) block, matched by balanced parentheses."""
    import re
    match = re.search(r"(?im)^\s*param\s*\(", text)
    if not match:
        return ""
    depth, start = 0, match.end() - 1
    for index in range(start, len(text)):
        depth += {"(": 1, ")": -1}.get(text[index], 0)
        if depth == 0:
            return text[start:index + 1]
    return text[start:]


def test_no_script_uses_its_own_path_inside_param_defaults():
    # Windows PowerShell 5.1 leaves $MyInvocation.MyCommand.Path empty there (Split-Path: argument is null).
    offenders = [str(path.relative_to(ROOT)) for path in ROOT.rglob("*.ps1")
                 if ".git" not in path.parts and "MyInvocation" in _param_block(path.read_text(encoding="utf-8"))]
    assert offenders == []


def test_inline_python_commands_avoid_double_quotes():
    # Windows PowerShell 5.1 strips " from arguments passed to programs, turning
    # acquire(".") into acquire(.) (a SyntaxError that looked like "TV Manager is running").
    import re
    offenders = []
    for path in ROOT.rglob("*.ps1"):
        if ".git" in path.parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for code in re.findall(r"-c\s+'((?:[^']|'')*)'", line):
                if '"' in code:
                    offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []


def test_install_auto_deploy_only_reports_running_when_tv_manager_says_so():
    setup = (ROOT / "install-auto-deploy.ps1").read_text(encoding="utf-8")
    assert "runtime_guard.acquire(os.getcwd())" in setup and "-match 'already running'" in setup
    assert "already running" in (ROOT / "runtime_guard.py").read_text(encoding="utf-8")


def test_startup_steps_write_to_log_files_with_time_limits():
    # Capturing db_doctor.py output through a PowerShell pipeline stalled it under the
    # scheduled task (no CPU, never finished); each step now writes to files with a limit.
    start = (ROOT / "start-production.ps1").read_text(encoding="utf-8")
    assert "| Out-String" not in start and "*> $null" not in start
    assert "-RedirectStandardOutput $out" in start and "WaitForExit($TimeoutMinutes * 60 * 1000)" in start
    assert "Invoke-StartupStep 'protect_db'" in start and "Invoke-StartupStep 'db_doctor'" in start
    assert auto_update.DEFAULTS["start_timeout_seconds"] >= 1500
    assert "start_timeout_seconds = 1500" in (ROOT / "install-auto-deploy.ps1").read_text(encoding="utf-8")
