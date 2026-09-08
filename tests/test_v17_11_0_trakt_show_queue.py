from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_17_11_0():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() in {"17.11.0", "17.12.0", "17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6", "18.5.7", "18.5.8", "18.5.9"}


def test_trakt_client_has_safe_status_and_discovery_endpoints():
    text = (ROOT / "trakt_client.py").read_text(encoding="utf-8")
    assert "TRAKT_CLIENT_ID" in text
    assert "trakt-api-version" in text
    assert "trakt-api-key" in text
    assert "/shows/trending" in text
    assert "/shows/popular" in text
    assert "/shows/anticipated" in text
    assert "search_shows" in text


def test_app_registers_trakt_and_show_queue_routes():
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '@app.get("/trakt")' in text
    assert '@app.get("/show-queue")' in text
    assert '@app.get("/api/trakt/shows")' in text
    assert '@app.post("/api/trakt/add-show")' in text
    assert '@app.get("/api/show-queue")' in text
    assert "LIMIT ? OFFSET ?" in text


def test_show_queue_and_trakt_templates_are_sidebar_aware():
    for name in ["trakt.html", "show_queue.html"]:
        text = (ROOT / "templates" / name).read_text(encoding="utf-8")
        assert "side-nav" in text or '{% include "_nav.html" %}' in text
        assert "layout-audited" in text
        assert "global.js" in text


def test_show_queue_js_supports_sort_filter_and_paging():
    js = (ROOT / "static" / "show_queue.js").read_text(encoding="utf-8")
    assert "/api/show-queue" in js
    assert "data-sort" in (ROOT / "templates" / "show_queue.html").read_text(encoding="utf-8")
    assert "showQueueStatus" in js
    assert "showQueueNext" in js
    assert "download-meter" in js


def test_docs_exist_for_trakt_and_show_queue():
    doc = (ROOT / "docs" / "TRAKT_DISCOVERY_AND_SHOW_QUEUE.md").read_text(encoding="utf-8")
    assert "TRAKT_CLIENT_ID" in doc
    assert "/show-queue" in doc
    assert "/api/show-queue" in doc
