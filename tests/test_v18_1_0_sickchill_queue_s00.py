from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]


def _load_queue_helpers():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index("def _normalize_queue_airdate")
    end = source.index('@app.get("/api/show-queue")')
    ns = {"datetime": datetime, "engine": object()}
    exec(source[start:end], ns)
    return ns


def test_version_is_18_1_0():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() in {"18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5"}


def test_sickchill_downloads_sort_prioritizes_missing_then_downloaded():
    helpers = _load_queue_helpers()
    rows = [
        {"name":"Complete Big","missing_count":0,"downloaded_count":100,"episode_count":100},
        {"name":"Needs Two","missing_count":2,"downloaded_count":20,"episode_count":22},
        {"name":"Needs Ten","missing_count":10,"downloaded_count":5,"episode_count":15},
        {"name":"Needs Ten More Downloaded","missing_count":10,"downloaded_count":30,"episode_count":40},
    ]
    out = helpers["_sort_show_queue_rows"](rows, "downloads", "desc")
    assert [r["name"] for r in out] == ["Needs Ten More Downloaded", "Needs Ten", "Needs Two", "Complete Big"]


def test_missing_display_compacts_episode_numbers():
    helpers = _load_queue_helpers()
    row = {"missing_count": 14, "missing_episode_numbers": ",".join([f"S01E{i:02d}" for i in range(1, 15)])}
    assert helpers["_queue_missing_display"](row, limit=3) == "S01E01, S01E02, S01E03 +11 more"
    assert helpers["_queue_missing_display"]({"missing_count": 0, "missing_episode_numbers": ""}) == "Complete"


def test_templates_and_js_expose_s00_ignore_and_missing_counts():
    settings = (ROOT / "templates" / "settings.html").read_text(encoding="utf-8")
    show_queue = (ROOT / "templates" / "show_queue.html").read_text(encoding="utf-8")
    queue_js = (ROOT / "static" / "queue.js").read_text(encoding="utf-8")
    show_queue_js = (ROOT / "static" / "show_queue.js").read_text(encoding="utf-8")
    assert "ignoreSeasonZeroCounts" in settings
    assert "Ignore Season 00" in settings
    assert "Missing / Downloads" in show_queue
    assert "missing_episode_numbers" in queue_js
    assert "S00 ignored" in queue_js
    assert "missing_display" in show_queue_js
