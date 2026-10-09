"""v18.17.0: Scan Show Folder on the show page; scans also mark vanished files missing."""
import json, os, shutil, subprocess, sys, tempfile, textwrap, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCENARIO = textwrap.dedent(r'''
    import json, sys, time
    from pathlib import Path
    import app, engine
    lib = Path(sys.argv[1]); offline = sys.argv[2] == "offline"
    show_dir = lib / "Good Show"; (show_dir / "Season 01").mkdir(parents=True)
    found = show_dir / "Season 01" / "Good Show - S01E02 - Two.mkv"; found.write_text("E2")
    gone = show_dir / "Season 01" / "Good Show - S01E01 - One.mkv"   # recorded but deleted
    with engine.cx() as c:
        c.execute("INSERT INTO shows(id,name,location,season_folders) VALUES(7,'Good Show',?,1)", (str(show_dir),))
        c.execute("INSERT INTO episodes(show_id,season,episode,name,status,location,file_size) VALUES(7,1,1,'One','Downloaded',?,10)", (str(gone),))
        c.execute("INSERT INTO episodes(show_id,season,episode,name,status) VALUES(7,1,2,'Two','Wanted')")
        c.commit()
    if offline:
        import shutil; shutil.rmtree(show_dir)   # show folder unreachable
    client = app.app.test_client()
    page = client.get("/show/7").get_data(as_text=True)
    r = client.post("/api/shows/7/scan-library/start", json={})
    job_id = r.get_json()["job"]["job_id"]
    for _ in range(100):
        job = client.get(f"/api/jobs/{job_id}").get_json()["job"]
        if job["status"] in ("complete", "error", "cancelled"): break
        time.sleep(0.1)
    with engine.cx() as c:
        eps = {r["episode"]: dict(r) for r in c.execute("SELECT episode,status,location FROM episodes WHERE show_id=7")}
    print(json.dumps({"page_has_button": 'id="scanShowFolder"' in page, "job": {k: job.get(k) for k in ("status", "message", "result", "error")}, "eps": eps}))
''')


def run_scenario(mode):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp); code = tmp / "app"
        shutil.copytree(ROOT, code, ignore=shutil.ignore_patterns(".git", "tests", "*.db*", "managed_trash", "logs", ".runtime", "__pycache__", "imports", "backups"))
        (code / "scenario.py").write_text(SCENARIO, encoding="utf-8")
        lib = tmp / "library"; lib.mkdir()
        out = subprocess.run([sys.executable, "scenario.py", str(lib), mode], cwd=code, capture_output=True, text=True, timeout=180,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if out.returncode != 0:
            raise AssertionError(out.stderr[-3000:])
        return json.loads(out.stdout.strip().splitlines()[-1])


class ShowFolderScanTests(unittest.TestCase):
    def test_scan_finds_files_and_marks_vanished_files_missing(self):
        r = run_scenario("online")
        self.assertTrue(r["page_has_button"])
        self.assertEqual(r["job"]["status"], "complete", r)
        self.assertEqual(r["eps"]["2"]["status"], "Downloaded")
        self.assertTrue(r["eps"]["2"]["location"].endswith("S01E02 - Two.mkv"))
        self.assertEqual(r["eps"]["1"]["status"], "Wanted")
        self.assertIsNone(r["eps"]["1"]["location"])
        self.assertEqual(r["job"]["result"]["cleared"], 1)
        self.assertEqual(r["job"]["result"]["cleared_episodes"], ["S01E01"])
        self.assertIn("no longer on disk", r["job"]["message"])

    def test_unreachable_show_folder_changes_nothing(self):
        r = run_scenario("offline")
        self.assertEqual(r["job"]["status"], "error", r)
        self.assertEqual(r["eps"]["1"]["status"], "Downloaded")
        self.assertIsNotNone(r["eps"]["1"]["location"])

    def test_page_script_wires_button(self):
        js = (ROOT / "static" / "show_detail.js").read_text(encoding="utf-8")
        self.assertIn("scanShowFolder", js)
        self.assertIn("/scan-library/start", js)


if __name__ == "__main__":
    unittest.main()
