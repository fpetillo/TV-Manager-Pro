from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_operations_scan_buttons_have_progress_panels_and_job_links():
    html = (ROOT / "templates" / "operations.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "operations.js").read_text(encoding="utf-8")
    assert "pathJobProgress" in html
    assert "conflictJobProgress" in html
    assert "fingerprintJobProgress" in html
    assert "snapshotJobProgress" in html
    for endpoint in [
        "/api/library/root-health/start",
        "/api/library/conflicts/start",
        "/api/library/fingerprint-conflicts/start",
        "/api/config-snapshots/start",
    ]:
        assert endpoint in js
    assert "progressHtml" in js
    assert "/jobs" in js
    assert "pollJob" in js


def test_show_scan_existing_files_uses_background_progress_job():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    js = (ROOT / "static" / "manager.js").read_text(encoding="utf-8")
    assert '@app.post("/api/shows/<int:sid>/scan-library/start")' in app
    assert 'run_background("show_folder_scan"' in app
    assert "progress_callback" in app
    assert "/scan-library/start" in js
    assert "Scan Existing Files queued" in js
    assert "pollJob" in js
