import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import episode_rules


def make_db(tmp_path: Path) -> Path:
    db = tmp_path / "tvmanager.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE shows(id INTEGER PRIMARY KEY, name TEXT, paused INTEGER DEFAULT 0, search_enabled INTEGER DEFAULT 1)")
    c.execute("""CREATE TABLE episodes(
        id INTEGER PRIMARY KEY, show_id INTEGER, season INTEGER, episode INTEGER,
        name TEXT, airdate TEXT, status TEXT, location TEXT, monitored INTEGER DEFAULT 1
    )""")
    c.execute("INSERT INTO shows(id,name) VALUES(1,'Blue Bloods')")
    rows = [
        (1, 1, 0, 1, 'Special Interview', '2020-01-01', 'Wanted', None, 1),
        (2, 1, 0, 2, 'Behind the Scenes', '2020-01-02', 'Wanted', None, 1),
        (3, 1, 1, 1, 'Pilot', '2020-02-01', 'Downloaded', 'pilot.mkv', 1),
        (4, 1, 1, 2, 'Second', '2020-02-08', 'Wanted', None, 1),
    ]
    c.executemany("INSERT INTO episodes(id,show_id,season,episode,name,airdate,status,location,monitored) VALUES(?,?,?,?,?,?,?,?,?)", rows)
    c.commit(); c.close()
    return db


def test_ignore_specials_marks_season_zero_ignored_and_unmonitored(tmp_path):
    db = make_db(tmp_path)
    result = episode_rules.ignore_specials(db, show_id=1)
    assert result["affected"] == 2
    with episode_rules.cx(db) as c:
        rows = c.execute("SELECT season, episode, status, monitored, ignored, ignored_reason FROM episodes ORDER BY id").fetchall()
    specials = [dict(r) for r in rows if r["season"] == 0]
    assert all(r["ignored"] == 1 for r in specials)
    assert all(r["monitored"] == 0 for r in specials)
    assert all(r["status"] == "Ignored" for r in specials)
    assert "Season 00" in specials[0]["ignored_reason"]


def test_ignored_episode_is_excluded_from_considered_filter(tmp_path):
    db = make_db(tmp_path)
    episode_rules.apply(db, {"show_id": 1, "episode_ids": [4]}, "ignore_selected", ignored=True, monitored=False, reason="Do not want recap")
    with episode_rules.cx(db) as c:
        considered = c.execute("SELECT COUNT(*) FROM episodes e WHERE e.show_id=1" + episode_rules.considered_sql("e")).fetchone()[0]
        all_count = c.execute("SELECT COUNT(*) FROM episodes WHERE show_id=1").fetchone()[0]
    assert all_count == 4
    assert considered == 3


def test_include_specials_restores_wanted_considered_counts(tmp_path):
    db = make_db(tmp_path)
    episode_rules.ignore_specials(db, show_id=1)
    result = episode_rules.include_specials(db, show_id=1)
    assert result["affected"] == 2
    with episode_rules.cx(db) as c:
        ignored = c.execute("SELECT COUNT(*) FROM episodes WHERE ignored=1").fetchone()[0]
        wanted = c.execute("SELECT COUNT(*) FROM episodes WHERE season=0 AND status='Wanted' AND monitored=1").fetchone()[0]
    assert ignored == 0
    assert wanted == 2


def test_preview_can_select_specials_or_selected_ids(tmp_path):
    db = make_db(tmp_path)
    specials = episode_rules.preview(db, {"show_id": 1, "specials": True})
    selected = episode_rules.preview(db, {"show_id": 1, "episode_ids": [3, 4]})
    assert specials["total"] == 2
    assert selected["total"] == 2
    assert selected["sample"][0]["show_name"] == "Blue Bloods"


def test_show_detail_static_contains_bulk_episode_controls():
    js = Path("static/show_detail.js").read_text()
    html = Path("templates/show_detail.html").read_text()
    assert "bulkIgnoreSelected" in js
    assert "bulkIncludeSpecials" in js
    assert "Ignored episodes stay visible" in html
    assert "/api/episodes/bulk/apply/start" in js
