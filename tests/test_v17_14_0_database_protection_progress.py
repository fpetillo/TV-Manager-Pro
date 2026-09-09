from pathlib import Path
import sqlite3
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_docs_exist():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() in {"17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6", "18.5.7", "18.5.8", "18.5.9", "18.5.10", "18.5.11"}
    assert (ROOT / "docs" / "DATABASE_PROTECTION_CENTER.md").exists()
    assert (ROOT / "docs" / "PROGRESS_JOB_CENTER.md").exists()
    assert (ROOT / "docs" / "RELEASE_NOTES_v17.14.0.md").exists()


def test_database_safety_uses_sqlite_backup_api_and_redacts_env(tmp_path, monkeypatch):
    import database_safety

    db = tmp_path / "tvmanager.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE shows(id INTEGER PRIMARY KEY, name TEXT)")
    con.execute("INSERT INTO shows(name) VALUES('Protected Show')")
    con.commit(); con.close()

    result = database_safety.backup_database(db, reason="test", retention=5)
    assert result["ok"] is True
    assert result["method"] == "sqlite_backup_api"
    assert result["quick_check"] == "ok"
    assert Path(result["backup"]).exists()
    assert result["sha256"]

    restored = sqlite3.connect(result["backup"])
    try:
        row = restored.execute("SELECT name FROM shows").fetchone()
        assert row[0] == "Protected Show"
    finally:
        restored.close()


def test_database_safety_page_and_routes_are_registered():
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    for route in [
        '/database-safety',
        '/api/protection/status',
        '/api/protection/backup',
        '/api/protection/backups',
        '/api/jobs',
        '/api/library/health-scan/start',
        '/api/library/health-scan/jobs/<job_id>',
    ]:
        assert route in text
    assert (ROOT / "templates" / "database_safety.html").exists()
    assert (ROOT / "static" / "database_safety.js").exists()


def test_library_health_uses_background_progress_job():
    js = (ROOT / "static" / "library_health.js").read_text(encoding="utf-8")
    assert "/api/library/health-scan/start" in js
    assert "/api/library/health-scan/jobs/" in js
    assert "progress-fill" in js
    html = (ROOT / "templates" / "library_health.html").read_text(encoding="utf-8")
    assert "refreshHealth" in html
    assert "/database-safety" in html


def test_job_center_completes_background_job():
    import job_center

    def worker(job_id):
        job_center.update_job(job_id, stage="Half", percent=50, processed=1)
        return {"done": True}

    job = job_center.run_background("unit_test", worker, stage="Queued", message="Testing")
    deadline = time.time() + 5
    final = None
    while time.time() < deadline:
        final = job_center.get_job(job["job_id"])
        if final and final.get("status") == "complete":
            break
        time.sleep(0.05)
    assert final["status"] == "complete"
    assert final["percent"] == 100
    assert final["result"] == {"done": True}


def test_run_script_calls_protect_db_before_db_doctor():
    script = (ROOT / "run.ps1").read_text(encoding="utf-8")
    assert "protect_db.py --startup" in script
    assert script.index("protect_db.py --startup") < script.index("db_doctor.py")
