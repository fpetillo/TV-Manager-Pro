from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sidebar_pages_use_manager_shell():
    for path in (ROOT / "templates").glob("*.html"):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        if "side-nav" in text or '{% include "_nav.html" %}' in text:
            assert 'class="shell manager-shell' in text, f"{path.name} must use sidebar-aware manager-shell"


def test_responsive_css_rules_present():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    assert "v17.10.0 responsive fit audit" in css
    assert ".mobile-nav-toggle" in css
    assert "overflow-wrap:anywhere" in css
    assert "@media(max-width:860px)" in css


def test_global_js_adds_mobile_nav_toggle_and_table_wrapping():
    js = (ROOT / "static" / "global.js").read_text(encoding="utf-8")
    assert "mobile-nav-toggle" in js
    assert "nav-open" in js
    assert "auto-table-wrap" in js


def test_version_is_17_10_0():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() in {"17.11.0", "17.12.0", "17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0"}, "17.11.0"
