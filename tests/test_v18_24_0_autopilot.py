"""v18.24.0: Missing Episode Autopilot, not-aired labels, blocked releases skipped at search time."""
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_in_copy(script_text: str, name="scenario.py") -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        app_dir = Path(tmp) / "app"
        shutil.copytree(ROOT, app_dir, ignore=shutil.ignore_patterns(
            ".git", "tests", "*.db*", "managed_trash", "logs", ".runtime", "__pycache__", "imports", "backups"))
        (app_dir / name).write_text(script_text, encoding="utf-8")
        r = subprocess.run([sys.executable, name], cwd=app_dir, capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, r.stderr[-3000:]
        return json.loads(r.stdout.strip().splitlines()[-1])


def test_end_to_end_search_grab_fail_retry_stall_and_set_aside():
    """Fake Newznab indexer and fake SABnzbd over real HTTP (tests/fixtures/autopilot_e2e_scenario.py)."""
    out = run_in_copy((ROOT / "tests" / "fixtures" / "autopilot_e2e_scenario.py").read_text(encoding="utf-8"))
    # Run 1: the Skipped and the Wanted aired episodes are searched and sent; not-aired and ignored are not.
    assert out["run1"]["searched"] == 2 and out["run1"]["sent_to_downloader"] == 2
    assert out["searched_eps"] == ["1", "2"]
    assert out["counts1"]["not_aired"] == 1
    assert all(u.endswith("-ALPHA.nzb") for u in out["sab1"])
    # Run 2: E01's download failed -> its release is blocked and a different release is sent in the same run.
    assert out["run2"]["failures"]["failed"] == 1
    assert out["run2"]["search"]["sent_to_downloader"] == 1 and out["run2"]["search"]["errors"] == []
    assert [d["release_name"] for d in out["dl2"] if d["episode"] == 1] == [
        "Good.Show.S01E01.1080p.WEB.h264-ALPHA", "Good.Show.S01E01.1080p.WEB.h264-BRAVO"]
    # Run 3: E02's download stalled for 13 hours -> blocked and replaced.
    assert out["run3"]["failures"]["stalled"] == 1 and out["run3"]["search"]["sent_to_downloader"] == 1
    assert out["dl3"][-1]["release_name"] == "Good.Show.S01E02.1080p.WEB.h264-BRAVO"
    # Run 4: E01 failed twice (max_attempts=2) -> set aside, not searched again.
    assert out["run4"]["failures"]["set_aside"] == 1 and out["run4"]["search"]["searched"] == 0
    assert [r["episode"] for r in out["status"]["set_aside"]] == [1]
    assert out["blocked"] == ["guid-S01E01-ALPHA", "guid-S01E01-BRAVO", "guid-S01E02-ALPHA"]
    # Retry puts it back into the rotation.
    assert out["retry"] == {"retried": 1} and out["after_retry_due"] == [1]


SCENARIO = textwrap.dedent(r'''
    import json
    from datetime import date, timedelta
    import app, engine, autopilot
    client = app.app.test_client()
    t = date.today()
    with engine.cx() as c:
        c.execute("INSERT INTO shows(id,name,location) VALUES(1,'Show A','/x')")
        c.execute("INSERT INTO shows(id,name,location,paused) VALUES(2,'Paused Show','/y',1)")
        eps = [(1,1,1,(t-timedelta(days=10)).isoformat(),"Skipped",""),
               (1,1,2,(t-timedelta(days=3)).isoformat(),"Wanted",""),
               (1,1,3,(t+timedelta(days=4)).isoformat(),"Wanted",""),
               (1,1,4,(t-timedelta(days=2)).isoformat(),"Downloaded","/x/S01E04.mkv"),
               (1,1,5,(t-timedelta(days=1)).isoformat(),"Archived",""),
               (1,1,6,None,"Wanted",""),
               (1,0,1,(t-timedelta(days=5)).isoformat(),"Wanted",""),
               (2,1,1,(t-timedelta(days=5)).isoformat(),"Wanted","")]
        for sid, s, e, air, st, loc in eps:
            c.execute("INSERT INTO episodes(show_id,season,episode,airdate,status,location,monitored) VALUES(?,?,?,?,?,?,1)", (sid,s,e,air,st,loc))
        c.commit()
    out = {}
    out["page"] = client.get("/autopilot").status_code
    out["nav"] = 'href="/autopilot"' in client.get("/dashboard").get_data(as_text=True)
    st = client.get("/api/autopilot/status").get_json()
    out["defaults"] = st["settings"]; out["counts"] = st["counts"]; out["running"] = st["running"]
    out["missing_api"] = sorted((r["season"], r["episode"]) for r in client.get("/api/missing").get_json()["results"])
    out["due"] = autopilot.eligible_episode_ids()
    autopilot.save_settings({"include_skipped": 0})
    out["due_no_skipped"] = autopilot.eligible_episode_ids()
    autopilot.save_settings({"include_skipped": 1, "include_lost_files": 1})
    out["due_lost"] = autopilot.eligible_episode_ids()
    out["bad"] = [client.post("/api/autopilot/settings", json=b).status_code for b in
                  ({"batch_size": 0}, {"interval_minutes": 2}, {"nope": 1}, {"retry_hours": "x"})]
    r = client.post("/api/autopilot/settings", json={"enabled": 1, "interval_minutes": 180, "batch_size": 75})
    st = r.get_json()
    out["on"] = [st["settings"]["enabled"], st["settings"]["interval_minutes"], st["settings"]["batch_size"], st["running"], st["automation_armed"]]
    engine.init_engine()   # a restart keeps the chosen interval
    out["after_restart"] = autopilot.status()["settings"]["interval_minutes"]
    out["off"] = client.post("/api/autopilot/settings", json={"enabled": 0}).get_json()["running"]
    out["retry_bad"] = client.post("/api/autopilot/retry", json={}).status_code
    # No indexer or download client: the run says so and leaves every episode due.
    before = autopilot.eligible_episode_ids()
    run = autopilot.run_cycle()
    out["unready"] = [run["steps"]["search"].get("skipped"), len(run.get("errors") or []), autopilot.eligible_episode_ids() == before]
    out["readiness"] = autopilot.status()["readiness"]["ready"]
    print(json.dumps(out))
''')


def test_missing_rules_settings_and_page():
    out = run_in_copy(SCENARIO)
    assert out["page"] == 200 and out["nav"] is True
    assert out["defaults"]["enabled"] == 0 and out["defaults"]["interval_minutes"] == 60 and out["running"] is False
    # Missing = aired + no file; excludes not-aired (S01E03), no air date (E06), specials (S00 rule),
    # paused shows, files present (E04) and Archived (unless lost files are included).
    assert out["missing_api"] == [[1, 1], [1, 2]]
    assert out["counts"]["missing"] == 2 and out["counts"]["not_aired"] == 1
    assert out["due"] == [2, 1]                 # never searched: newest air date first
    assert out["due_no_skipped"] == [2]
    assert out["due_lost"] == [5, 2, 1]
    assert out["bad"] == [400, 400, 400, 400]
    assert out["on"] == [1, 180, 75, True, True]
    assert out["after_restart"] == 180
    assert out["off"] is False
    assert out["retry_bad"] == 400
    assert out["unready"] == [True, 2, True] and out["readiness"] is False


def test_show_page_labels_not_aired_episodes():
    js = (ROOT / "static" / "show_detail.js").read_text(encoding="utf-8")
    start = js.index("function localToday")
    end = js.index("function fmtDate")
    fmt_end = js.index("\n", end)
    script = js[start:fmt_end] + "\n" + textwrap.dedent('''
        const esc=v=>String(v);
        const d=new Date(); const iso=x=>{const y=new Date(d);y.setDate(y.getDate()+x);return `${y.getFullYear()}-${String(y.getMonth()+1).padStart(2,'0')}-${String(y.getDate()).padStart(2,'0')}`};
        console.log(JSON.stringify([fileStateLabel({airdate:iso(3)}),fileStateLabel({airdate:iso(0)}),fileStateLabel({airdate:iso(-3)}),fileStateLabel({airdate:''})]));
    ''')
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    future, today, past, none = json.loads(r.stdout)
    assert "Not aired yet" in future and "Missing" in today and "Missing" in past and "No air date" in none


def test_blocked_releases_are_rejected_during_search():
    src = (ROOT / "engine.py").read_text(encoding="utf-8")
    assert 'x["rejected_reason"]="Failed before (blocked release)"' in src
