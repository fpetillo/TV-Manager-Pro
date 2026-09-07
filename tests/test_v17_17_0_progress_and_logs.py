from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_docs_exist_for_17_17_0():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() in {"17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1"}
    assert (ROOT / "docs" / "RELEASE_NOTES_v17.18.0.md").exists()
    assert (ROOT / "docs" / "PROGRESS_EVERYWHERE_AND_LOGS.md").exists()


def test_subtitle_audit_has_background_progress_route_and_ui():
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    js = (ROOT / "static" / "subtitles.js").read_text(encoding="utf-8")
    assert '/api/subtitles/scan/start' in app_text
    assert 'job_center.run_background("subtitle_audit"' in app_text
    assert '/api/jobs/' in js
    assert 'progressHtml' in js


def test_postprocess_preview_scan_has_background_progress():
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    js = (ROOT / "static" / "postprocess.js").read_text(encoding="utf-8")
    engine_text = (ROOT / "engine.py").read_text(encoding="utf-8")
    assert '/api/postprocess/scan/start' in app_text
    assert 'job_center.run_background("postprocess_scan"' in app_text
    assert '/api/postprocess/scan/start' in js
    assert 'progress_callback' in engine_text


def test_downloader_handoff_has_progress_and_monitoring():
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    js = (ROOT / "static" / "show_detail.js").read_text(encoding="utf-8")
    assert '/api/search-results/<int:rid>/grab/start' in app_text
    assert 'job_center.run_background("downloader_handoff"' in app_text
    assert '/grab/start' in js
    assert 'download-handoff-progress' in js


def test_logs_viewer_filtering_sorting_exists():
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    engine_text = (ROOT / "engine.py").read_text(encoding="utf-8")
    html = (ROOT / "templates" / "logs.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "logs.js").read_text(encoding="utf-8")
    assert '@app.get("/logs")' in app_text
    assert '@app.get("/api/logs")' in app_text
    assert 'def activity_filtered' in engine_text
    assert 'logLevel' in html and 'logEvent' in html and 'logSort' in html
    assert 'data-sort' in js and '/api/logs?' in js
