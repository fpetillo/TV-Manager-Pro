from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_version_is_18_3_1():
    assert read("VERSION").strip() in {"18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6", "18.5.7", "18.5.8", "18.5.9", "18.5.10", "18.5.11", "18.5.12", "18.5.13", "18.5.15"}


def test_global_specials_endpoints_exist():
    app = read("app.py")
    assert '@app.post("/api/episodes/specials/global-preview")' in app
    assert '@app.post("/api/episodes/specials/global-ignore/start")' in app
    assert '@app.post("/api/episodes/specials/global-include/start")' in app
    assert 'ignore_season_zero_counts", "1"' in app


def test_s00_specials_are_excluded_from_wanted_and_search_processing():
    engine = read("engine.py")
    assert 'ignore_specials_from_wanted' in engine
    assert 'specials_wanted_sql' in engine
    assert 'COALESCE(e.season,-1)<>0' in engine
    assert 'Season 00 / Specials are globally hidden from Missing/Wanted' in engine


def test_manage_page_has_one_place_global_specials_control():
    html = read("templates/manage.html")
    js = read("static/manage.js")
    assert 'Season 00 / Specials' in html
    assert 'Ignore S00 / Specials Everywhere' in html
    assert 'Include S00 / Specials Again' in html
    assert '/api/episodes/specials/global-ignore/start' in js
    assert '/api/episodes/specials/global-include/start' in js


def test_backlog_and_summary_respect_global_s00_rule():
    parity = read("sickchill_parity.py")
    lifecycle = read("lifecycle.py")
    assert '_specials_clause' in parity
    assert '{specials}' in parity
    assert '_setting_bool("TVManager", "ignore_season_zero_counts", True)' in lifecycle
