"""v18.27.0: browser icon (favicon, touch icon, web manifest) on every page."""
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / 'static' / 'icons'


def test_icon_files_exist_and_are_valid():
    from PIL import Image
    ico = Image.open(ICONS / 'favicon.ico')
    assert {(16, 16), (32, 32), (48, 48)} <= set(ico.ico.sizes())
    for name, size in [('apple-touch-icon.png', 180), ('icon-192.png', 192), ('icon-512.png', 512)]:
        assert Image.open(ICONS / name).size == (size, size)
    assert (ICONS / 'tv-manager.svg').read_text(encoding='utf-8').lstrip().startswith('<svg')


def test_every_page_template_links_the_icon():
    pages = [p for p in (ROOT / 'templates').glob('*.html') if '<head' in p.read_text(encoding='utf-8')]
    assert len(pages) > 30
    for page in pages:
        html = page.read_text(encoding='utf-8')
        assert 'rel="icon" href="/static/icons/tv-manager.svg"' in html, page.name
        assert 'href="/favicon.ico"' in html and 'rel="apple-touch-icon"' in html and 'rel="manifest"' in html, page.name


SCENARIO = textwrap.dedent(r'''
    import json
    import app, security
    security.set_admin_password("admin", "icon-test-password-123")
    security.set_browser_auth(True)  # every non-public page now needs login
    client = app.app.test_client()
    dashboard = client.get("/dashboard")
    ico = client.get("/favicon.ico")
    manifest = client.get("/site.webmanifest")
    svg = client.get("/static/icons/tv-manager.svg")
    login = client.get("/login")
    print(json.dumps({"dashboard": dashboard.status_code,
                      "ico": [ico.status_code, ico.mimetype, ico.data[:4].hex()],
                      "manifest": [manifest.status_code, manifest.headers.get("Content-Type"), manifest.get_json()],
                      "svg": svg.status_code,
                      "login_icon": 'rel="icon"' in login.get_data(as_text=True)}))
''')


def test_icon_routes_are_served_without_login():
    with tempfile.TemporaryDirectory() as tmp:
        code = Path(tmp) / 'app'
        shutil.copytree(ROOT, code, ignore=shutil.ignore_patterns(
            '.git', 'tests', '*.db*', 'managed_trash', 'logs', '.runtime', '__pycache__', 'imports', 'backups'))
        (code / 'scenario.py').write_text(SCENARIO, encoding='utf-8')
        r = subprocess.run([sys.executable, 'scenario.py'], cwd=code, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, r.stderr[-3000:]
        out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out['dashboard'] in (302, 303)  # login really is required
    assert out['ico'] == [200, 'image/vnd.microsoft.icon', '00000100']
    status, content_type, manifest = out['manifest']
    assert status == 200 and content_type.startswith('application/manifest+json')
    assert manifest['name'] == 'TV Manager' and {i['sizes'] for i in manifest['icons']} == {'192x192', '512x512', 'any'}
    assert out['svg'] == 200 and out['login_icon']
