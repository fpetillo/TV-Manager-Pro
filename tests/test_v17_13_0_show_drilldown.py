from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_version_is_17_13_0():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() in {"17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6", "18.5.7", "18.5.8", "18.5.9", "18.5.10", "18.5.11", "18.5.12", "18.5.13", "18.5.14"}

def test_show_queue_links_to_show_detail():
    js = (ROOT / "static" / "show_queue.js").read_text(encoding="utf-8")
    assert 'href="/show/${r.id}"' in js
    assert '/show/${r.id}' in js

def test_show_detail_page_and_assets_exist():
    html = (ROOT / "templates" / "show_detail.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "show_detail.js").read_text(encoding="utf-8")
    assert '/show/<show_id>' not in html
    assert 'episodeSearch' in html
    assert 'episode-drill-table' in html
    assert '/api/shows/${showId}/episodes?' in js
    assert 'searchEpisode' in js
    assert 'grabSearchResult' in js

def test_app_registers_show_detail_and_paged_episodes():
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '@app.get("/show/<int:sid>")' in text
    assert 'def show_detail_page(sid):' in text
    assert 'all_mode=' in text
    assert 'has_more=offset+limit<total' in text

def test_docs_exist():
    assert (ROOT / "docs" / "SHOW_DETAIL_DRILLDOWN.md").exists()
    assert (ROOT / "docs" / "RELEASE_NOTES_v17.13.0.md").exists()
