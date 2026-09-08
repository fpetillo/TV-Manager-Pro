from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v17_19_version_and_docs():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() in {"17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6"}
    assert (ROOT / "docs" / "RELEASE_NOTES_v17.20.0.md").exists()
    assert (ROOT / "docs" / "DOWNLOADER_VALIDATION_CENTER.md").exists()


def test_download_center_page_and_navigation_exist():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    nav = (ROOT / "templates" / "_nav.html").read_text(encoding="utf-8")
    tpl = (ROOT / "templates" / "download_center.html").read_text(encoding="utf-8")
    assert '@app.get("/download-center")' in app
    assert 'download_center.html' in app
    assert 'Download Center' in nav
    assert 'href="/download-center"' in nav
    assert 'Downloader handoff verification' in tpl
    assert '/static/download_center.js' in tpl


def test_downloader_monitor_apis_and_background_jobs_exist():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    engine = (ROOT / "engine.py").read_text(encoding="utf-8")
    for route in [
        '/api/downloaders/monitor',
        '/api/downloaders/readiness',
        '/api/downloaders/test/start',
        '/api/downloaders/poll/start',
        '/api/downloads/monitor/start',
    ]:
        assert route in app
    assert 'def downloader_monitor(' in engine
    assert 'def downloader_readiness_check(' in engine
    assert 'downloader_connection_test' in app
    assert 'downloader_queue_poll' in app
    assert 'download_monitor_refresh' in app


def test_download_center_js_has_progress_and_handoff_monitoring():
    js = (ROOT / "static" / "download_center.js").read_text(encoding="utf-8")
    assert '/api/downloaders/monitor' in js
    assert '/api/downloaders/test/start' in js
    assert '/api/downloaders/poll/start' in js
    assert '/api/search-results/' in js and '/grab/start' in js
    assert 'progress-track' in js
    assert 'handoffCandidates' in js


def test_launchpad_readiness_explains_loading_state():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    tpl = (ROOT / "templates" / "launchpad.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "launchpad.js").read_text(encoding="utf-8")
    assert 'readiness_explanation' in app
    assert 'readiness_label' in app
    assert 'readinessExplain' in tpl
    assert 'Replacement readiness could not load' in js
    assert 'Downloader Check' in tpl
