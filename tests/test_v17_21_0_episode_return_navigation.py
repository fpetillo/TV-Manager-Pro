from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_show_detail_has_return_navigation_controls():
    js = (ROOT / 'static' / 'show_detail.js').read_text(encoding='utf-8')
    assert 'Back to Episodes' in js
    assert 'returnToEpisodes' in js
    assert 'rememberEpisodePosition' in js
    assert 'Sent to downloader. Returned to the episode list.' in js


def test_show_detail_links_to_download_monitoring():
    html = (ROOT / 'templates' / 'show_detail.html').read_text(encoding='utf-8')
    assert '/download-center' in html
    assert '/jobs' in html
    assert 'return here automatically after queueing' in html


def test_release_notes_document_episode_navigation():
    doc = (ROOT / 'docs' / 'RELEASE_NOTES_v17.21.0.md').read_text(encoding='utf-8')
    assert 'Automatic return to the episode list' in doc
    assert 'Back to Episodes' in doc
