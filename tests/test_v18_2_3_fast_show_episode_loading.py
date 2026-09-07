from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')

def test_show_detail_has_fast_and_quick_paths():
    app = read('app.py')
    assert 'fast=(request.args.get("fast")' in app
    assert 'quick=(request.args.get("quick")' in app
    assert 'SELECT {cols} FROM episodes' in app
    assert 'fetch_limit=limit+1' in app
    assert 'SELECT COUNT(*) FROM episodes{where_sql}' in app

def test_show_detail_js_does_not_block_whole_page_on_counts():
    js = read('static/show_detail.js')
    assert '/api/shows/${showId}?fast=1' in js
    assert 'quick:\'1\'' in js
    assert ('Promise.allSettled' in js or 'loadShow().then' in js)
    assert 'loadShowCountsFast' in js
    assert ('kept the screen responsive' in js or 'stopped waiting instead of hanging' in js)

def test_subtitle_scan_has_network_skip_and_candidate_limit():
    eng = read('engine.py')
    assert 'subtitle_scan_max_candidates' in eng
    assert 'subtitle_scan_network_paths' in eng
    assert '_is_probably_remote_media_path' in eng
    assert 'SkippedRemote' in eng
