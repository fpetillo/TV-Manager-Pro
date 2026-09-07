from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_release_notes():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() in {"17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2"}
    assert (ROOT / "docs" / "RELEASE_NOTES_v17.20.0.md").exists()


def test_dbcore_has_process_writer_lock_and_retry_guard():
    src = (ROOT / "dbcore.py").read_text(encoding="utf-8")
    assert "_WRITE_LOCK = threading.RLock()" in src
    assert "DEFAULT_BUSY_TIMEOUT_MS = 120000" in src
    assert "def retry(" in src
    assert "database is locked" in src
    assert "_tvmanager_write_locked" in src


def test_engine_scheduler_and_logging_are_lock_safe():
    src = (ROOT / "engine.py").read_text(encoding="utf-8")
    assert "dbcore.retry(write_db" in src
    assert "emergency.log" in src
    assert "dbcore.retry(write_finish" in src
    assert "scheduler_finish_error" in src


def test_media_server_full_maintenance_routes_exist():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '@app.get("/api/media-servers/<int:sid>")' in app
    assert '@app.delete("/api/media-servers/<int:sid>")' in app
    assert '@app.post("/api/media-servers/<int:sid>/test/start")' in app
    assert '@app.post("/api/media-servers/<int:sid>/refresh/start")' in app
    assert '@app.post("/api/media-servers/<int:sid>/sync-watched/start")' in app


def test_advanced_ui_has_edit_delete_media_controls_and_job_monitoring():
    js = (ROOT / "static" / "advanced.js").read_text(encoding="utf-8")
    assert "editMedia" in js
    assert "deleteMedia" in js
    assert "test/start" in js
    assert "refresh/start" in js
    assert "sync-watched/start" in js
    assert "watchJob" in js
    assert "deleteProvider" in js
    assert "deleteWebhook" in js
    assert "deleteGroup" in js
