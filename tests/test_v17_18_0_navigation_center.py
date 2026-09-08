from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v17_18_version_and_docs():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() in {"17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6"}
    assert (ROOT / "docs" / "RELEASE_NOTES_v17.18.0.md").exists()
    assert (ROOT / "docs" / "NAVIGATION_CENTER.md").exists()


def test_navigation_include_has_professional_sections_and_log_access():
    nav = (ROOT / "templates" / "_nav.html").read_text(encoding="utf-8")
    assert 'nav-v18' in nav
    for label in ["Command Center", "Logs & Events", "Active Jobs", "Database Safety", "Manage Center", "Show Queue", "Post Processing", "Trakt Discover"]:
        assert label in nav
    for href in ['/logs', '/jobs', '/database-safety', '/manage', '/show-queue', '/postprocess', '/settings']:
        assert f'href="{href}"' in nav
    assert 'data-nav-badge="jobs"' in nav
    assert 'data-nav-badge="logs"' in nav
    assert 'id="navFilter"' in nav


def test_templates_use_shared_navigation_include():
    include = '{% include "_nav.html" %}'
    checked = 0
    for template in (ROOT / "templates").glob("*.html"):
        if template.name in {"login.html", "security_setup.html", "_nav.html"}:
            continue
        text = template.read_text(encoding="utf-8")
        if include in text:
            checked += 1
    assert checked >= 20


def test_global_navigation_script_supports_collapsible_filter_badges():
    js = (ROOT / "static" / "global.js").read_text(encoding="utf-8")
    assert "professional navigation center" in js
    assert "navFilter" in js
    assert "nav-section-toggle" in js
    assert "/api/jobs" in js
    assert "/api/logs" in js
    assert "/api/protection/status" in js


def test_navigation_css_for_professional_sidebar():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    assert "v17.18.0 professional navigation" in css
    assert ".nav-quick-actions" in css
    assert ".nav-filter" in css
    assert ".nav-section-toggle" in css
    assert "badge-warn" in css
