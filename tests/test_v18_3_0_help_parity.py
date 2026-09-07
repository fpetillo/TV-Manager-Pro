from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]

def load_help_content():
    spec = importlib.util.spec_from_file_location('help_content', ROOT / 'help_content.py')
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules['help_content'] = mod
    spec.loader.exec_module(mod)
    return mod

def test_help_center_routes_are_registered():
    app = (ROOT / 'app.py').read_text()
    assert '@app.get("/help")' in app
    assert '@app.get("/help/<slug>")' in app
    assert '@app.get("/api/help")' in app
    assert '@app.get("/api/help/sickchill-parity")' in app
    assert '@app.get("/api/product/workflow-map")' in app


def test_navigation_exposes_help_center():
    nav = (ROOT / 'templates' / '_nav.html').read_text()
    assert 'Help Center' in nav
    assert 'data-nav-version="{{ app_version }}"' in nav


def test_help_content_has_sickchill_parity_matrix():
    mod = load_help_content()
    summary = mod.parity_summary()
    assert summary['total'] >= 18
    assert summary['counts']['Complete'] >= 8
    assert any(item['area'] == 'Episodes' and 'Specials' in item['sickchill_feature'] for item in summary['items'])
    assert any(item['status'] == 'Partial' for item in summary['items'])


def test_help_topics_cover_core_flows():
    mod = load_help_content()
    slugs = {item['slug'] for item in mod.help_index()}
    for required in ['getting-started','show-queue','episode-management','ignore-rules','download-center','post-processing','subtitles','troubleshooting']:
        assert required in slugs


def test_help_frontend_fetches_expected_apis():
    js = (ROOT / 'static' / 'help.js').read_text()
    assert "/api/help" in js
    assert "/api/help/sickchill-parity" in js
    assert "workflowCards" in js
    assert "parityRows" in js
