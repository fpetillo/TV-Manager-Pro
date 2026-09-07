from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_docs_exist_for_17_16_0():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() in {"17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3"}
    assert (ROOT / "docs" / "SICKCHILL_PARITY_MANAGE.md").exists()
    assert (ROOT / "docs" / "RELEASE_NOTES_v17.16.0.md").exists()
    assert (ROOT / "templates" / "manage.html").exists()
    assert (ROOT / "static" / "manage.js").exists()
    assert (ROOT / "sickchill_parity.py").exists()


def test_app_registers_sickchill_manage_routes_and_apis():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    for token in [
        '@app.get("/manage")',
        '@app.get("/api/manage/summary")',
        '@app.get("/api/manage/backlog-overview")',
        '@app.post("/api/manage/episode-status/preview")',
        '@app.post("/api/manage/episode-status/apply")',
        '@app.get("/api/manage/failed-downloads")',
        '@app.get("/api/manage/missed-subtitles")',
        '@app.get("/api/manage/scene-exceptions")',
        '@app.post("/api/manage/mass-refresh/start")',
    ]:
        assert token in src


def test_sickchill_parity_module_covers_manage_surfaces():
    src = (ROOT / "sickchill_parity.py").read_text(encoding="utf-8")
    for token in [
        "backlog_overview",
        "status_preview",
        "status_apply",
        "failed_downloads",
        "missed_subtitles",
        "scene_exceptions",
        "mass_update_history",
    ]:
        assert token in src


def test_manage_ui_has_sickchill_style_sections_and_progress():
    html = (ROOT / "templates" / "manage.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "manage.js").read_text(encoding="utf-8")
    for phrase in [
        "Backlog Overview",
        "Episode Status Management",
        "Failed Downloads",
        "Missed Subtitle Management",
        "Scene Exceptions",
        "Mass Refresh",
    ]:
        assert phrase in html
    assert "pollJob" in js
    assert "progress-fill" in js
    assert "/api/search/run/${kind}/start" in js


def test_navigation_and_command_palette_include_manage():
    settings = (ROOT / "templates" / "settings.html").read_text(encoding="utf-8")
    nav = (ROOT / "templates" / "_nav.html").read_text(encoding="utf-8")
    intel = (ROOT / "intelligence.py").read_text(encoding="utf-8")
    assert '{% include "_nav.html" %}' in settings
    assert 'href="/manage"' in nav
    assert "SickChill Manage" in intel
    assert "Scene Exceptions" in intel
