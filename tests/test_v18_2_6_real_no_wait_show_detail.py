from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')

def test_show_detail_js_uses_explicit_dom_bindings_not_browser_id_globals():
    js = read('static/show_detail.js')
    assert "const $id=(id)=>document.getElementById(id);" in js
    assert "const showHeader=$id('showHeader')" in js
    assert "const episodeBody=$id('episodeBody')" in js
    assert "const bulkIgnoreSpecials=$id('bulkIgnoreSpecials')" in js

def test_show_detail_js_real_no_wait_first_paint_and_fast_watchdog():
    js = read('static/show_detail.js')
    assert 'real no-wait first paint' in js
    assert "Show screen ready" in js
    assert "Ready to load episodes" in js
    assert "const generation=++seasonGeneration" in js
    assert "episodeLimit.value='50'" in js
    assert 'timeout:10000' in js

def test_show_detail_has_snapshot_and_lite_endpoints():
    app = read('app.py')
    assert '@app.get("/api/shows/<int:sid>/snapshot")' in app
    assert '@app.get("/api/shows/<int:sid>/episodes-lite")' in app
    assert 'timeout=0.15' in app
    assert 'LIMIT ? OFFSET ?' in app
