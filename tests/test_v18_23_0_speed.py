"""v18.23.0: speed work (writer lock, cached checks, file checks, indexes, compression, intervals)."""
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import dbcore  # noqa: E402
import episode_dates  # noqa: E402


def run_in_copy(code: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        app_dir = Path(tmp) / "app"
        shutil.copytree(ROOT, app_dir, ignore=shutil.ignore_patterns(
            ".git", "tests", "*.db*", "managed_trash", "logs", ".runtime", "__pycache__", "imports", "backups"))
        (app_dir / "scenario.py").write_text(textwrap.dedent(code), encoding="utf-8")
        r = subprocess.run([sys.executable, "scenario.py"], cwd=app_dir, capture_output=True, text=True, timeout=240)
        assert r.returncode == 0, r.stderr[-3000:]
        return json.loads(r.stdout.strip().splitlines()[-1])


# ------------------------------------------------------------------ writer lock
def test_statement_classifier():
    reads = ["SELECT 1", " select * from x", "PRAGMA busy_timeout=5", "PRAGMA journal_mode=WAL", "PRAGMA table_info(x)",
             "PRAGMA user_version", "WITH t AS (SELECT 1) SELECT updated_at FROM t", "EXPLAIN QUERY PLAN SELECT 1"]
    writes = ["INSERT INTO a VALUES(1)", "UPDATE a SET b=1", "DELETE FROM a", "BEGIN IMMEDIATE", "CREATE INDEX i ON t(x)",
              "PRAGMA wal_checkpoint(TRUNCATE)", "PRAGMA optimize", "PRAGMA user_version=3", "ANALYZE", "VACUUM",
              "WITH t AS (SELECT 1)\nDELETE FROM a WHERE id IN t"]
    assert [q for q in reads if dbcore._is_write(q)] == []
    assert [q for q in writes if not dbcore._is_write(q)] == []


def test_reads_do_not_wait_for_a_writer_and_writes_still_queue(tmp_path):
    db = tmp_path / "t.db"
    with dbcore.connect(db) as c:
        c.execute("CREATE TABLE n(id INTEGER PRIMARY KEY, v INTEGER)")
        c.execute("INSERT INTO n VALUES(1,0)")
    started = threading.Event()

    def writer():
        with dbcore.connect(db) as w:
            w.execute("UPDATE n SET v=v+1 WHERE id=1")
            started.set()
            time.sleep(1.5)

    t = threading.Thread(target=writer)
    t.start()
    started.wait(5)
    s = time.perf_counter()
    with dbcore.connect(db) as r:  # writable connection that only reads
        r.execute("SELECT v FROM n").fetchone()
    read_wait = time.perf_counter() - s
    s = time.perf_counter()
    with dbcore.connect(db) as w2:
        w2.execute("UPDATE n SET v=v+1 WHERE id=1")
    write_wait = time.perf_counter() - s
    t.join()
    assert read_wait < 0.5, read_wait
    assert write_wait > 1.0, write_wait  # the second writer waited for the first
    with dbcore.connect(db, readonly=True) as r:
        assert r.execute("SELECT v FROM n").fetchone()[0] == 2


def test_concurrent_writers_lose_nothing(tmp_path):
    db = tmp_path / "t.db"
    with dbcore.connect(db) as c:
        c.execute("CREATE TABLE n(id INTEGER PRIMARY KEY, v INTEGER)")
        c.execute("INSERT INTO n VALUES(1,0)")
    errors = []

    def work():
        try:
            for _ in range(40):
                with dbcore.connect(db) as c:
                    c.execute("BEGIN IMMEDIATE")
                    v = c.execute("SELECT v FROM n WHERE id=1").fetchone()[0]
                    c.execute("UPDATE n SET v=? WHERE id=1", (v + 1,))
                with dbcore.connect(db) as c:
                    c.execute("UPDATE n SET v=v+1 WHERE id=1")
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    threads = [threading.Thread(target=work) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    with dbcore.connect(db, readonly=True) as r:
        assert r.execute("SELECT v FROM n").fetchone()[0] == 6 * 40 * 2
    assert dbcore._WRITE_LOCK.acquire(timeout=1)  # the lock is free again
    dbcore._WRITE_LOCK.release()


def test_write_lock_released_on_exception(tmp_path):
    db = tmp_path / "t.db"
    try:
        with dbcore.connect(db) as c:
            c.execute("CREATE TABLE x(a)")
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    got = []

    def other():
        ok = dbcore._WRITE_LOCK.acquire(timeout=1)
        got.append(ok)
        if ok:
            dbcore._WRITE_LOCK.release()

    t = threading.Thread(target=other)
    t.start()
    t.join()
    assert got == [True]


# ------------------------------------------------------------------ dates
def test_sql_date_expression_matches_python():
    con = sqlite3.connect(":memory:")
    con.create_function("episode_airdate", 1, episode_dates.normalize)
    expr = episode_dates.sql_expr("v")
    for value in ["2024-05-06", "2024-05-06 21:00:00", "2024-05-06T21:00", "737203", "05/06/2024", "", None, "0", "20240506"]:
        got = con.execute(f"SELECT {expr} FROM (SELECT ? v)", (value,)).fetchone()[0]
        assert (got or "") == episode_dates.normalize(value), value


# ------------------------------------------------------------------ file checks
def test_files_present_lists_each_folder_once(tmp_path, monkeypatch):
    import library_maintenance as lm
    season = tmp_path / "Show" / "Season 01"
    season.mkdir(parents=True)
    (season / "Show - S01E01.mkv").write_text("x")
    (season / "Show - S01E02.mkv").write_text("x")
    calls = []
    real = lm._list_folder
    monkeypatch.setattr(lm, "_list_folder", lambda f: calls.append(f) or real(f))
    paths = [str(season / "Show - S01E01.mkv"), str(season / "Show - S01E02.mkv"), str(season / "Show - S01E03.mkv"),
             str(tmp_path / "Gone" / "a.mkv"), "", str(season)]
    assert lm.files_present(paths) == [True, True, False, False, False, False]
    assert sorted(calls) == sorted({str(season), str(tmp_path / "Gone"), str(tmp_path / "Show")})


# ------------------------------------------------------------------ app-level
def test_app_speed_features():
    out = run_in_copy(r'''
        import json, gzip
        import app, engine, database_safety, library_maintenance, ops, performance
        client = app.app.test_client()
        with engine.cx() as c:
            for i in range(1, 41):
                c.execute("INSERT INTO shows(id,name,location) VALUES(?,?,?)", (i, f"Show {i}", f"/nowhere/Show {i}"))
                for e in range(1, 6):
                    c.execute("INSERT INTO episodes(show_id,season,episode,name,status,location,airdate) VALUES(?,?,?,?,?,?,?)",
                              (i, 1, e, "E", "Downloaded", f"/nowhere/Show {i}/Season 01/S01E0{e}.mkv", "2020-01-0%d" % e))
            c.executemany("INSERT INTO activity_log(level,event_type,message,created_at) VALUES(?,?,?,?)",
                          [("ERROR" if i % 3 == 0 else "info", "search", "m", "2020-01-01 00:00:00" if i < 50 else "2099-01-01 00:00:00") for i in range(100)])
        out = {}
        with engine.cx() as c:
            names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        out["indexes"] = sorted(n for n in names if n in {"idx_activity_level_nocase", "idx_activity_event_nocase", "idx_downloads_status"})
        b = client.get("/api/nav/badges").get_json()
        out["badges"] = {k: b[k] for k in ("active_jobs", "errors", "database_ok")}
        logs = client.get("/api/logs?level=error&limit=5").get_json()
        out["logs"] = [logs["total"], logs["levels"], logs["event_types"]]
        calls = []
        real = database_safety.quick_check
        database_safety.quick_check = lambda p=database_safety.DB: calls.append(1) or real(p)
        database_safety._LIVE_CHECK.clear()
        client.get("/api/protection/status"); first = len(calls)
        client.get("/api/protection/status"); client.get("/api/system/health"); client.get("/api/nav/badges")
        out["quick_checks"] = [first >= 1, len(calls) - first]
        database_safety.quick_check = real
        built = []
        real_report = library_maintenance.library_health_report
        library_maintenance.library_health_report = lambda *a, **k: built.append(1) or real_report(*a, **k)
        library_maintenance.clear_report_cache()
        for p in ("/api/launchpad/summary", "/api/setup/summary", "/api/workflow/summary", "/api/dashboard/full"):
            assert client.get(p).status_code == 200, p
        out["reports_built"] = len(built)
        library_maintenance.library_health_report = real_report
        out["missing_files"] = library_maintenance.library_health_report(engine.DB)["counts"]["missing_episode_files"]
        lookups = []
        real_pm = ops.path_mappings
        ops.path_mappings = lambda: lookups.append(1) or real_pm()
        client.get("/api/library/conflicts"); out["mapping_lookups_conflicts"] = len(lookups); lookups.clear()
        client.get("/api/library/root-health"); out["mapping_lookups_roots"] = len(lookups)
        ops.path_mappings = real_pm
        r = client.get("/api/shows", headers={"Accept-Encoding": "gzip"})
        out["gzip"] = [r.headers.get("Content-Encoding"), json.loads(gzip.decompress(r.data)) is not None]
        r = client.get("/api/shows")
        out["plain"] = r.headers.get("Content-Encoding")
        r = client.get("/static/style.css?v=1", headers={"Accept-Encoding": "gzip"})
        out["static"] = [r.headers.get("Cache-Control"), r.headers.get("Content-Encoding"), len(gzip.decompress(r.data)) > 10000]
        r = client.get("/static/style.css")
        out["static_unversioned"] = r.headers.get("Cache-Control")
        with engine.cx() as c:
            out["pruned"] = performance.prune_logs(c, engine.get_setting)
            out["left"] = c.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0]
        engine.set_setting("TVManager", "activity_log_retention_days", "0")
        with engine.cx() as c:
            out["pruned_off"] = performance.prune_logs(c, engine.get_setting)
        assert client.post("/api/scheduler/jobs/backlog_search", json={"interval": 360}).status_code == 200
        engine.init_engine()
        with engine.cx() as c:
            out["backlog_interval"] = c.execute("SELECT interval_minutes FROM scheduler_jobs WHERE name='backlog_search'").fetchone()[0]
        print(json.dumps(out))
    ''')
    assert out["indexes"] == ["idx_activity_event_nocase", "idx_activity_level_nocase", "idx_downloads_status"]
    assert out["badges"]["database_ok"] is True and out["badges"]["errors"] == 34 and out["badges"]["active_jobs"] >= 0
    assert out["logs"][0] == 34 and set(out["logs"][1]) == {"ERROR", "info"} and out["logs"][2] == ["search"]
    assert out["quick_checks"] == [True, 0]  # later requests reuse the live check and unchanged backups
    assert out["reports_built"] == 1
    assert out["missing_files"] == 200
    assert out["mapping_lookups_conflicts"] == 1 and out["mapping_lookups_roots"] == 1
    assert out["gzip"] == ["gzip", True] and out["plain"] is None
    assert out["static"] == ["public, max-age=31536000, immutable", "gzip", True]
    assert "max-age=3600" in (out["static_unversioned"] or "")
    assert out["pruned"] == {"activity_log": 50} and out["left"] == 50 and out["pruned_off"] == {}
    assert out["backlog_interval"] == 360


def test_menu_uses_single_badge_request():
    js = (ROOT / "static" / "global.js").read_text(encoding="utf-8")
    block = js[js.index("async function refreshBadges"):]
    block = block[:block.index("\n  }\n")]
    assert "/api/nav/badges" in block and "/api/protection/status" not in block and "/api/logs" not in block
    assert "document.hidden" in block
