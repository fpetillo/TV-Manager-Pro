"""v18.22.0: interface themes (Classic, Glassy, Midnight, Daylight)."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ui_themes  # noqa: E402

THEMES_CSS = (ROOT / "static" / "themes.css").read_text(encoding="utf-8")

SCENARIO = textwrap.dedent(r'''
    import json
    import app
    client = app.app.test_client()
    out = {}
    out["default"] = client.get("/api/ui/theme").get_json()
    out["default_page"] = client.get("/dashboard").get_data(as_text=True)
    out["bad"] = [client.post("/api/ui/theme", json={"theme": "neon"}).status_code,
                  client.post("/api/ui/theme", json={}).status_code]
    out["saved"] = client.post("/api/ui/theme", json={"theme": "Glassy"}).get_json()
    out["after"] = client.get("/api/ui/theme").get_json()["theme"]
    out["dashboard"] = client.get("/dashboard").get_data(as_text=True)
    out["about"] = client.get("/about").get_data(as_text=True)
    out["login"] = client.get("/login", follow_redirects=True).get_data(as_text=True)
    import ui_themes, engine
    ui_themes._cached = None   # a restart reads the saved value back from the database
    out["reloaded"] = ui_themes.current()
    out["stored"] = engine.get_setting("ui", "theme")
    print(json.dumps(out))
''')


def run_scenario():
    with tempfile.TemporaryDirectory() as tmp:
        code = Path(tmp) / "app"
        shutil.copytree(ROOT, code, ignore=shutil.ignore_patterns(
            ".git", "tests", "*.db*", "managed_trash", "logs", ".runtime", "__pycache__", "imports", "backups"))
        (code / "scenario.py").write_text(SCENARIO, encoding="utf-8")
        r = subprocess.run([sys.executable, "scenario.py"], cwd=code, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, r.stderr[-3000:]
        return json.loads(r.stdout.strip().splitlines()[-1])


def test_theme_setting_api_and_pages():
    out = run_scenario()
    assert out["default"]["theme"] == "classic"
    assert [t["id"] for t in out["default"]["themes"]] == ["classic", "glassy", "midnight", "daylight"]
    assert '<html data-theme="classic">' in out["default_page"]
    assert out["bad"] == [400, 400]
    assert out["saved"]["ok"] and out["saved"]["theme"] == "glassy"
    assert out["after"] == "glassy"
    for page in ("dashboard", "about", "login"):
        assert '<html data-theme="glassy">' in out[page], page
        assert "/static/themes.css?v=" in out[page], page
    # The picker in the menu lists every theme and marks the saved one.
    picker = out["dashboard"][out["dashboard"].index('id="uiThemeSelect"'):]
    picker = picker[:picker.index("</select>")]
    assert re.findall(r'<option value="(\w+)"', picker) == ["classic", "glassy", "midnight", "daylight"]
    assert re.search(r'<option value="glassy"[^>]*selected', picker)
    assert out["reloaded"] == "glassy" and out["stored"] == "glassy"


def test_every_page_template_loads_themes():
    for path in sorted((ROOT / "templates").glob("*.html")):
        html = path.read_text(encoding="utf-8")
        if "<html" not in html:
            continue  # partials such as _nav.html
        assert '<html data-theme="{{ ui_theme }}">' in html, path.name
        assert '<link rel="stylesheet" href="/static/themes.css?v={{ app_version }}">' in html, path.name
        assert html.index("/static/style.css") < html.index("/static/themes.css"), path.name


def test_generated_stylesheet_is_current():
    r = subprocess.run([sys.executable, "scripts/build_themes.py", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_generated_stylesheet_content():
    for theme in ("glassy", "midnight", "daylight"):
        assert f'html[data-theme="{theme}"] body{{background:' in THEMES_CSS, theme
    assert 'html[data-theme="classic"]' not in THEMES_CSS  # Classic is style.css itself
    assert "backdrop-filter:blur(22px)" in THEMES_CSS
    assert 'html[data-theme="daylight"]{background:#eef3fa;color-scheme:light}' in THEMES_CSS
    assert "@keyframes" not in THEMES_CSS
    # Every selector is scoped to a theme.
    body = re.sub(r"/\*.*?\*/", "", THEMES_CSS, flags=re.S)
    for selector_list in re.findall(r"(?:^|})\s*([^{}@]+)\{", body):
        for sel in re.sub(r":is\([^)]*\)", ":is()", selector_list).split(","):
            if sel.strip():
                assert sel.strip().startswith('html[data-theme="'), sel


def test_colour_mapping_rules():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_themes as b
    C = b.Color.parse
    # Daylight turns dark surfaces light and light text dark, and keeps accent buttons.
    assert b.daylight(C("#131a25"), "bg").hls()[1] > 0.9
    assert b.daylight(C("#edf3fb"), "text").hls()[1] < 0.2
    assert b.daylight(C("#3a78ff"), "bg").css() == "#3a78ff"
    assert b.daylight(C("#f5c518"), "text").hls()[1] < 0.4   # gold readable on white
    # Glassy makes opaque dark surfaces translucent but leaves text alone.
    assert b.glassy(C("#131a25"), "bg").a < 0.2
    assert b.glassy(C("#aeb9ca"), "text").css() == "#aeb9ca"
    # Midnight darkens and neutralises surfaces.
    h, l, s = b.midnight(C("#131a25"), "bg").hls()
    assert l < 0.06 and s < 0.1
    # Text on an accent button is kept in every theme.
    decls = [("background", "#3a78ff"), ("color", "#fff")]
    assert b.role_of("color", b.rule_has_accent_bg(decls)) == "keep"


def test_theme_module():
    assert ui_themes.normalize("GLASSY") == "glassy"
    assert ui_themes.normalize("nope") == "classic"
    assert list(ui_themes.THEMES) == ["classic", "glassy", "midnight", "daylight"]


def test_picker_script_saves_and_reverts():
    js = (ROOT / "static" / "global.js").read_text(encoding="utf-8")
    block = js[js.index("v18.22.0"):]
    assert "select[data-theme-picker]" in block and "/api/ui/theme" in block
    assert "root.dataset.theme=previous" in block  # a failed save restores the previous theme


def test_settings_page_text_is_not_double_encoded():
    for rel in ("templates/settings.html", "static/settings-v5.js"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert not re.search("[ÂÃâ][\u0080-¿ŒœŸ‘-„€™]", text), rel
    assert "⌘ Search TV Manager" in (ROOT / "templates" / "settings.html").read_text(encoding="utf-8")
