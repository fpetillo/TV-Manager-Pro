from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_subtitle_scan_releases_db_lock_and_has_safety_limit():
    src = (ROOT / "engine.py").read_text(encoding="utf-8")
    assert "def subtitle_scan(show_id=None, progress_callback=None, max_seconds=None" in src
    assert "with cx(readonly=True) as c:" in src
    assert "subtitle_scan_max_seconds" in src
    assert "flush_updates" in src
    assert "dbcore.retry" in src
    assert "partial" in src


def test_readonly_connections_fast_fail_for_ui_reads():
    src = (ROOT / "dbcore.py").read_text(encoding="utf-8")
    assert ("DEFAULT_READ_BUSY_TIMEOUT_MS = 5000" in src or "DEFAULT_READ_BUSY_TIMEOUT_MS = 1200" in src)
    assert "DEFAULT_READ_TIMEOUT_SECONDS" in src
    assert "if readonly:" in src
    assert "timeout=DEFAULT_READ_TIMEOUT_SECONDS" in src


def test_show_detail_uses_readonly_and_timeout_message():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    js = (ROOT / "static" / "show_detail.js").read_text(encoding="utf-8")
    assert "with cx(readonly=True) as c:" in app
    assert "AbortController" in js
    assert ("Show load is taking too long" in js or "stopped waiting instead of hanging" in js)
