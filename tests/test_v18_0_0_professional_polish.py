from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_version_18_identity_and_docs():
    assert read("VERSION").strip() in {"18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1"}
    assert (ROOT / "docs" / "RELEASE_NOTES_v18.0.0.md").exists()
    assert (ROOT / "docs" / "VERSION_18_READINESS.md").exists()
    assert (ROOT / "docs" / "GITHUB_RELEASE_AUTOMATION.md").exists()


def test_launchpad_version_18_readiness_panel():
    html = read("templates/launchpad.html")
    js = read("static/launchpad.js")
    assert "version18Readiness" in html
    assert "version18Checklist" in html
    assert "/api/system/release-readiness" in js
    assert "loadReleaseReadiness" in js


def test_release_readiness_api_contract_present():
    app = read("app.py")
    assert '@app.get("/api/system/release-readiness")' in app
    for key in ["progress_everywhere", "operations_progress", "show_queue_sort", "download_center", "database_safety", "release_push", "v18_docs"]:
        assert key in app


def test_safe_release_push_script_protects_runtime_files():
    script = read("release-and-push.ps1")
    for token in ["tvmanager.db", ".env", "dist", "build", "release", "backups", "diagnostics", "managed_trash", "imports"]:
        assert token in script
    assert "git add -- ." in script
    assert "git push" in script


def test_navigation_and_show_queue_v18_polish():
    nav = read("templates/_nav.html")
    show_queue = read("templates/show_queue.html")
    css = read("static/style.css")
    assert 'data-nav-version="{{ app_version }}"' in nav
    assert "Version 18" in nav
    assert "actual downloaded count" in show_queue
    assert "v18.0.0 professional polish" in css
