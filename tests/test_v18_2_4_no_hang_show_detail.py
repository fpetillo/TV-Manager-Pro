from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_show_detail_uses_fast_seasons_endpoint_and_short_timeouts():
    js = (ROOT / "static" / "show_detail.js").read_text(encoding="utf-8")
    assert "/seasons-fast" in js
    assert ("timeout:900" in js or "timeout:1800" in js)
    assert ("timeout:750" in js or "timeout:2500" in js)
    assert "Retry episodes" in js
    assert "Detailed counts are optional" in js


def test_fast_seasons_endpoint_exists_and_is_non_blocking():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '@app.get("/api/shows/<int:sid>/seasons-fast")' in app
    assert "SELECT DISTINCT season FROM episodes" in app
    assert "return jsonify(error=str(e),seasons=[],fast=True),200" in app


def test_fallback_server_threaded_and_read_timeout_fast():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    dbcore = (ROOT / "dbcore.py").read_text(encoding="utf-8")
    assert "threaded=True" in app
    assert "debug=False" in app
    assert "DEFAULT_READ_BUSY_TIMEOUT_MS = 1200" in dbcore
