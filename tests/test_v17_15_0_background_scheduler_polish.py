from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_docs_exist_for_17_15_0():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() in {"17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1"}
    assert (ROOT / "docs" / "BACKGROUND_JOBS_AND_SCHEDULER.md").exists()
    assert (ROOT / "docs" / "RELEASE_NOTES_v17.15.0.md").exists()
    assert (ROOT / "templates" / "jobs.html").exists()
    assert (ROOT / "static" / "jobs.js").exists()


def test_background_job_endpoints_are_registered():
    app_py = (ROOT / "app.py").read_text(encoding="utf-8")
    for route in [
        '/jobs',
        '/api/jobs/<job_id>',
        '/api/episodes/<int:eid>/search/start',
        '/api/search/run/<kind>/start',
        '/api/shows/<int:sid>/refresh/start',
        '/api/postprocess/run/start',
        '/api/metadata/refresh/missing/start',
        '/api/metadata/artwork/start',
    ]:
        assert route in app_py


def test_scheduler_has_missing_metadata_artwork_and_safety_jobs():
    engine_py = (ROOT / "engine.py").read_text(encoding="utf-8")
    for name in [
        'missing_metadata',
        'artwork_refresh',
        'library_health_scan',
        'database_protection',
    ]:
        assert name in engine_py
    assert 'metadata_service.refresh_missing_metadata' in engine_py
    assert 'metadata_service.refresh_artwork' in engine_py
    assert 'database_safety.protect_now' in engine_py


def test_episode_artwork_schema_and_metadata_refresh_support():
    src = (ROOT / "metadata_service.py").read_text(encoding="utf-8")
    for token in ['still_url', 'still_path', 'tmdb_episode_id', 'metadata_updated_at']:
        assert token in src
        assert token in (ROOT / "db_doctor.py").read_text(encoding="utf-8")
    assert 'def missing_metadata_preview' in src
    assert 'def start_missing_metadata_refresh' in src
    assert 'def artwork_preview' in src
    assert 'def start_artwork_refresh' in src


def test_ui_uses_progress_bars_for_long_running_actions():
    show_js = (ROOT / "static" / "show_detail.js").read_text(encoding="utf-8")
    library_js = (ROOT / "static" / "library_health.js").read_text(encoding="utf-8")
    post_js = (ROOT / "static" / "postprocess.js").read_text(encoding="utf-8")
    settings_js = (ROOT / "static" / "settings-v5.js").read_text(encoding="utf-8")
    assert '/search/start' in show_js
    assert '/refresh/start' in show_js
    assert 'progress-fill' in show_js
    assert '/api/metadata/refresh/missing/start' in library_js
    assert '/api/metadata/artwork/start' in library_js
    assert '/api/postprocess/run/start' in post_js
    assert 'pollSchedulerJob' in settings_js
