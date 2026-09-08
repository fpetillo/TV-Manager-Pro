from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]


def _load_queue_helpers():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index("def _normalize_queue_airdate")
    end = source.index("@app.get(\"/api/show-queue\")")
    ns = {"datetime": datetime}
    exec(source[start:end], ns)
    return ns


def test_version_is_17_23_0():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() in {"17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6"}


def test_downloads_sort_uses_sickchill_missing_priority_descending():
    helpers = _load_queue_helpers()
    rows = [
        {"name": "Zero Big", "downloaded_count": 0, "episode_count": 33, "missing_count": 33, "size_bytes": 0},
        {"name": "Partial", "downloaded_count": 1, "episode_count": 9, "missing_count": 8, "size_bytes": 1},
        {"name": "Complete Three", "downloaded_count": 3, "episode_count": 3, "missing_count": 0, "size_bytes": 2},
        {"name": "Complete Four", "downloaded_count": 4, "episode_count": 4, "missing_count": 0, "size_bytes": 3},
    ]
    sorted_rows = helpers["_sort_show_queue_rows"]("rows" and rows, "downloads", "desc")
    assert [r["name"] for r in sorted_rows] == ["Zero Big", "Partial", "Complete Four", "Complete Three"]


def test_downloads_sort_uses_numeric_downloaded_count_ascending():
    helpers = _load_queue_helpers()
    rows = [
        {"name": "Complete Four", "downloaded_count": 4, "episode_count": 4, "missing_count": 0},
        {"name": "Zero Big", "downloaded_count": 0, "episode_count": 33, "missing_count": 33},
        {"name": "Partial", "downloaded_count": 1, "episode_count": 9, "missing_count": 8},
    ]
    sorted_rows = helpers["_sort_show_queue_rows"](rows, "downloads", "asc")
    assert [r["missing_count"] for r in sorted_rows] == [0, 8, 33]


def test_percent_and_size_sort_are_numeric():
    helpers = _load_queue_helpers()
    rows = [
        {"name": "Half", "downloaded_count": 5, "episode_count": 10, "size_bytes": 500},
        {"name": "Full Small", "downloaded_count": 1, "episode_count": 1, "size_bytes": 100},
        {"name": "None Huge", "downloaded_count": 0, "episode_count": 20, "size_bytes": 9000},
    ]
    assert [r["name"] for r in helpers["_sort_show_queue_rows"](rows, "download_percent", "desc")] == ["Full Small", "Half", "None Huge"]
    assert [r["name"] for r in helpers["_sort_show_queue_rows"](rows, "size", "desc")] == ["None Huge", "Half", "Full Small"]


def test_legacy_ordinal_dates_are_normalized_for_queue_display():
    helpers = _load_queue_helpers()
    assert helpers["_normalize_queue_airdate"]("737203") == "2019-05-24"
    assert helpers["_normalize_queue_airdate"]("1") == ""


def test_show_queue_js_uses_descending_default_for_downloads():
    js = (ROOT / "static" / "show_queue.js").read_text(encoding="utf-8")
    assert "numericDefaultDesc" in js
    assert "'downloads'" in js
    assert "aria-sort" in js
