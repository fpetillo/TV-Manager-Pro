from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_show_detail_has_loading_progress_contract():
    html = (ROOT / 'templates' / 'show_detail.html').read_text(encoding='utf-8')
    js = (ROOT / 'static' / 'show_detail.js').read_text(encoding='utf-8')
    css = (ROOT / 'static' / 'style.css').read_text(encoding='utf-8')
    assert 'Loading show' in html
    assert 'progress-track indeterminate' in html
    assert 'showPageLoading' in js
    assert 'episodeLoadingRow' in js
    assert ('Loading episode rows' in js or 'Opening first page quickly' in js)
    assert 'tvmIndeterminate' in css


def test_show_queue_open_show_has_visible_loading_indicator():
    js = (ROOT / 'static' / 'show_queue.js').read_text(encoding='utf-8')
    assert 'showQueueNavigationLoading' in js
    assert 'queueNavigationLoading' in js
    assert 'show-open-link' in js
    assert 'Opening ${esc(name' in js
