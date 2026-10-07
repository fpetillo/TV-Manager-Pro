"""v18.13.0: Show Queue file scans, top Post Processing shortcut, compact main pages, Trakt filters."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import sqlite3
import time

import pytest
from flask import Flask, jsonify, request

import advanced
import engine
import job_center
import trakt_client

ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")


def _db(tmp_path):
    path = tmp_path / "v18130.db"

    @contextmanager
    def cx():
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    return cx


# ---------------------------------------------------------------- Show Queue scan

def _scan_app(tmp_path):
    cx = _db(tmp_path)
    library = tmp_path / "library"
    with cx() as c:
        c.executescript(
            "CREATE TABLE shows(id INTEGER PRIMARY KEY,name,location);"
            "CREATE TABLE episodes(id INTEGER PRIMARY KEY,show_id,season,episode,location,file_size,status);"
        )
        for sid, name in ((1, "Alpha Show"), (2, "Beta Show"), (3, "No Folder")):
            if sid != 3:
                (library / name / "Season 01").mkdir(parents=True)
            c.execute("INSERT INTO shows VALUES(?,?,?)", (sid, name, str(library / name) if sid != 3 else ""))
            for ep in range(1, 4):
                c.execute("INSERT INTO episodes(show_id,season,episode,location,file_size,status) VALUES(?,?,?,'',0,'Wanted')", (sid, 1, ep))
    (library / "Alpha Show" / "Season 01" / "Alpha.Show.S01E01.1080p.mkv").write_bytes(b"x" * 10)
    (library / "Alpha Show" / "Season 01" / "Alpha.Show.S01E02.1080p.mkv").write_bytes(b"x" * 10)
    (library / "Beta Show" / "Season 01" / "Beta.Show.S01E03.720p.mkv").write_bytes(b"x" * 10)
    app = Flask(__name__)
    fake_engine = SimpleNamespace(episode_pattern=engine.episode_pattern, log=lambda *a, **k: None)
    ns = dict(app=app, request=request, jsonify=jsonify, cx=cx, engine=fake_engine, advanced=advanced,
              integrity=SimpleNamespace(cache_fingerprint=lambda f: None), job_center=job_center)
    exec(APP_SOURCE[APP_SOURCE.index("def _scan_show_library_impl"):APP_SOURCE.index('@app.get("/api/health")')], ns)
    return app.test_client(), cx


def _wait(job_id):
    deadline = time.time() + 10
    while time.time() < deadline:
        job = job_center.get_job(job_id)
        if job and job.get("status") in ("complete", "error", "cancelled"):
            return job
        time.sleep(0.05)
    raise AssertionError("scan job did not finish")


@pytest.fixture
def default_worker_limit(monkeypatch):
    monkeypatch.setattr(job_center, "worker_limit", lambda: 4)


def test_bulk_scan_updates_selected_shows_and_reports_failures(tmp_path, default_worker_limit):
    client, cx = _scan_app(tmp_path)
    response = client.post("/api/shows/scan-library/start", json={"show_ids": [1, "2", 3, 1, 999]})
    assert response.status_code == 200
    job = _wait(response.get_json()["job"]["job_id"])
    assert job["status"] == "complete"
    result = job["result"]
    assert [s["id"] for s in result["shows"]] == [1, 2, 3]  # duplicates and unknown ids dropped, order kept
    assert result["matched"] == 3 and result["failed"] == 1
    assert "no library folder" in result["shows"][2]["error"]
    with cx() as c:
        downloaded = c.execute("SELECT show_id,episode FROM episodes WHERE status='Downloaded' ORDER BY show_id,episode").fetchall()
    assert [tuple(r) for r in downloaded] == [(1, 1), (1, 2), (2, 3)]


@pytest.mark.parametrize("body,status", [({}, 400), ({"show_ids": "1"}, 400), ({"show_ids": ["x"]}, 400), ({"show_ids": [999]}, 404)])
def test_bulk_scan_rejects_bad_selections(tmp_path, body, status):
    client, _ = _scan_app(tmp_path)
    assert client.post("/api/shows/scan-library/start", json=body).status_code == status


def test_single_show_scan_route_is_unchanged(tmp_path):
    client, _ = _scan_app(tmp_path)
    data = client.post("/api/shows/2/scan-library").get_json()
    assert data["matched"] == 1 and data["show"] == "Beta Show"


def test_show_queue_page_exposes_row_and_selected_scans():
    html = (ROOT / "templates" / "show_queue.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "show_queue.js").read_text(encoding="utf-8")
    assert 'id="showQueueScanSelected"' in html and '<th scope="col">Files</th>' in html
    assert "scan-show-files" in js and "/api/shows/scan-library/start" in js
    assert "resolutionControls.selected" in js
    assert 'colspan="10"' not in js and 'colspan="10"' not in html


# ---------------------------------------------------------------- Post Processing shortcut

def test_post_processing_shortcut_is_injected_on_every_navigated_page():
    js = (ROOT / "static" / "global.js").read_text(encoding="utf-8")
    assert "global-postprocess-link" in js and "link.href='/postprocess'" in js
    for template in (ROOT / "templates").glob("*.html"):
        text = template.read_text(encoding="utf-8")
        if '{% include "_nav.html" %}' in text and template.name != "about.html":
            assert "global.js" in text, f"{template.name} would miss the Post Processing shortcut"
    # /about is served by the script-free support page; it carries a plain link instead.
    assert 'href="/postprocess">Post Processing</a>' in (ROOT / "support_routes.py").read_text(encoding="utf-8")
    assert ".global-postprocess-link{position:fixed" in (ROOT / "static" / "style.css").read_text(encoding="utf-8")


# ---------------------------------------------------------------- Compact main pages

def test_launchpad_and_dashboard_use_compact_top_cards():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    for name in ("launchpad.html", "dashboard.html"):
        assert "compact-home" in (ROOT / "templates" / name).read_text(encoding="utf-8")
    assert ".compact-home .launch-hero" in css and ".compact-home .kpi" in css
    assert ".compact-home #installationChecks" in css


# ---------------------------------------------------------------- Trakt filters

def test_years_filter_builds_trakt_ranges_and_rejects_bad_input():
    assert trakt_client.years_filter() == ""
    assert trakt_client.years_filter("2020", "2024") == "2020-2024"
    assert trakt_client.years_filter("2022", "2022") == "2022"
    assert trakt_client.years_filter("2015", "") == "2015-2100"
    assert trakt_client.years_filter("", "2010") == "1900-2010"
    for bad in (("20x0", ""), ("1800", ""), ("2024", "2020")):
        with pytest.raises(ValueError):
            trakt_client.years_filter(*bad)


def _trakt_app(tmp_path, pages):
    cx = _db(tmp_path)
    with cx() as c:
        c.executescript("CREATE TABLE shows(id INTEGER PRIMARY KEY,name,trakt_id,imdb_id,tmdb_id,tvdb_id,first_air_date);")
        c.execute("INSERT INTO shows(name,imdb_id,first_air_date) VALUES('Owned By Id','tt1','')")
        c.execute("INSERT INTO shows(name,first_air_date) VALUES('Owned: By Title!','2019-05-01')")
    calls = []

    def discover(category, page, limit, years=""):
        calls.append((category, page, limit, years))
        return [dict(r) for r in pages.get(page, [])]

    fake = SimpleNamespace(discover=discover, search_shows=lambda *a: [], years_filter=trakt_client.years_filter, status=lambda: {"configured": True})
    app = Flask(__name__)
    ns = dict(app=app, request=request, jsonify=jsonify, cx=cx, trakt_client=fake, re=__import__("re"))
    exec(APP_SOURCE[APP_SOURCE.index("TRAKT_HIDE_LIBRARY_MAX_PAGES="):APP_SOURCE.index('@app.post("/api/trakt/add-show")')], ns)
    return app.test_client(), calls


def _row(i, **extra):
    row = dict(trakt_id=i, name=f"Show {i}", year=2020, imdb_id=None, tmdb_id=None, tvdb_id=None)
    row.update(extra)
    return row


def test_trakt_marks_library_shows_by_id_or_title_and_year(tmp_path):
    page = [_row(1, imdb_id="tt1"), _row(2, name="Owned By Title", year=2019), _row(3)]
    client, calls = _trakt_app(tmp_path, {1: page})
    data = client.get("/api/trakt/shows?limit=3").get_json()
    assert [r["saved"] for r in data["results"]] == [True, True, False]
    assert data["hidden_in_library"] == 0 and calls == [("trending", 1, 3, "")]


def test_trakt_hide_library_pages_forward_to_fill_the_limit(tmp_path):
    pages = {1: [_row(1, imdb_id="tt1"), _row(2)], 2: [_row(3), _row(4)], 3: [_row(5), _row(6)]}
    client, calls = _trakt_app(tmp_path, pages)
    data = client.get("/api/trakt/shows?limit=2&hide_library=1&year_from=2018&year_to=2021").get_json()
    assert [r["trakt_id"] for r in data["results"]] == [2, 3]
    assert data["hidden_in_library"] == 1 and data["pages_checked"] == 2 and data["next_page"] == 3
    assert data["years"] == "2018-2021" and all(call[3] == "2018-2021" for call in calls)


def test_trakt_bad_year_is_reported_without_calling_trakt(tmp_path):
    client, calls = _trakt_app(tmp_path, {})
    response = client.get("/api/trakt/shows?year_from=2024&year_to=2020")
    assert response.status_code == 400 and "From year" in response.get_json()["error"] and calls == []


def test_trakt_page_has_library_toggle_and_year_controls():
    html = (ROOT / "templates" / "trakt.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "trakt.js").read_text(encoding="utf-8")
    for element in ("traktHideLibrary", "traktYearFrom", "traktYearTo", "traktMore"):
        assert f'id="{element}"' in html
    assert "hide_library" in js and "year_from" in js and "next_page" in js


def test_job_worker_limit_defaults_before_settings_table_exists(monkeypatch):
    def missing(*args, **kwargs):
        raise sqlite3.OperationalError("no such table: settings")

    monkeypatch.setattr(engine, "get_setting", missing)
    assert job_center.worker_limit() == 4
