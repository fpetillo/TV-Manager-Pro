"""v18.15.0: Post Processing "Replace anyway" for files blocked by the quality rule."""
import json, os, shutil, subprocess, sys, tempfile, textwrap, unittest
from pathlib import Path

import lifecycle

ROOT = Path(__file__).resolve().parents[1]

SCENARIO = textwrap.dedent(r'''
    import json, sys
    from pathlib import Path
    import app, engine, lifecycle
    lib = Path(sys.argv[1]); dl = Path(sys.argv[2]); mode = sys.argv[3]
    show_dir = lib / "Good Show"; (show_dir / "Season 01").mkdir(parents=True)
    old = show_dir / "Season 01" / "Good Show - S01E01 - Pilot.mkv"
    old.write_text("WRONG SHOW CONTENT")
    incoming = dl / "Good.Show.S01E01.1080p.WEB-DL.mkv"
    incoming.write_text("CORRECT EPISODE")
    with engine.cx() as c:
        c.execute("INSERT INTO shows(id,name,location,season_folders) VALUES(7,'Good Show',?,1)", (str(show_dir),))
        c.execute("INSERT INTO episodes(show_id,season,episode,name,status,location,quality,release_name) VALUES(7,1,1,'Pilot','Downloaded',?,'1080p WEB-DL','Good.Show.S01E01.1080p.WEB-DL')", (str(old),))
        c.commit()
    engine.set_setting("General", "naming_pattern", "Season %0S/%SN - S%0SE%0E - %EN")
    engine.set_setting("TVManager", "refresh_media_servers_after_process", "0")
    preview = engine.scan_postprocess(dry_run=True, root_override=str(dl))
    force = [str(incoming)] if mode == "force" else None
    run = engine.scan_postprocess(dry_run=False, root_override=str(dl), selected_sources=[str(incoming)], force_replace_sources=force)
    with engine.cx() as c:
        ep = dict(c.execute("SELECT location,release_name FROM episodes WHERE show_id=7").fetchone())
        reps = [dict(r) for r in c.execute("SELECT status,trash_path FROM upgrade_replacements")]
        events = [r[0] for r in c.execute("SELECT event_type FROM events")] if c.execute("SELECT name FROM sqlite_master WHERE name='events'").fetchone() else []
    print(json.dumps({"preview": preview["actions"], "run": run["actions"], "errors": run.get("errors"),
                      "processed": run.get("processed_count"), "old_content": old.read_text() if old.exists() else None,
                      "incoming_exists": incoming.exists(), "episode": ep, "replacements": reps,
                      "trash_content": [Path(r["trash_path"]).read_text() for r in reps if r["trash_path"] and Path(r["trash_path"]).exists()]}))
''')


def run_scenario(mode):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        code = tmp / "app"
        shutil.copytree(ROOT, code, ignore=shutil.ignore_patterns(".git", "tests", "*.db*", "managed_trash", "logs", ".runtime", "__pycache__", "imports", "backups"))
        (code / "scenario.py").write_text(SCENARIO, encoding="utf-8")
        lib, dl = tmp / "library", tmp / "downloads"
        lib.mkdir(); dl.mkdir()
        out = subprocess.run([sys.executable, "scenario.py", str(lib), str(dl), mode], cwd=code,
                             capture_output=True, text=True, timeout=180, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if out.returncode != 0:
            raise AssertionError(out.stderr[-3000:])
        return json.loads(out.stdout.strip().splitlines()[-1])


class ReplaceOverrideTests(unittest.TestCase):
    def test_same_quality_is_still_blocked_without_override(self):
        r = run_scenario("normal")
        self.assertIn("not higher quality", r["preview"][0]["blocked"])
        self.assertTrue(r["preview"][0]["can_override"])
        self.assertTrue(r["preview"][0]["existing_files"])
        self.assertEqual(r["processed"], 0)
        self.assertEqual(r["old_content"], "WRONG SHOW CONTENT")
        self.assertTrue(r["incoming_exists"])

    def test_replace_anyway_replaces_and_keeps_original_in_trash(self):
        r = run_scenario("force")
        self.assertEqual(r["processed"], 1, r)
        self.assertFalse(r["errors"], r["errors"])
        self.assertTrue(r["run"][0]["replace_override"])
        self.assertIn("not higher quality", r["run"][0]["override_reason"])
        self.assertEqual(r["old_content"], "CORRECT EPISODE")
        self.assertFalse(r["incoming_exists"])
        self.assertEqual([x["status"] for x in r["replacements"]], ["Completed"])
        self.assertEqual(r["trash_content"], ["WRONG SHOW CONTENT"])

    def test_stage_replacement_force_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "a.mkv"; old.write_text("x")
            ep = {"id": 1, "location": str(old), "quality": "1080p WEB-DL", "release_name": "A.S01E01.1080p.WEB-DL"}
            blocked = lifecycle.stage_replacement(ep, Path(tmp) / "b.mkv", "A.S01E01.720p.HDTV", "720p HDTV")
            self.assertFalse(blocked["allowed"])
            self.assertTrue(old.exists())

    def test_ui_offers_replace_anyway(self):
        js = (ROOT / "static" / "postprocess.js").read_text(encoding="utf-8")
        self.assertIn("pp-override", js)
        self.assertIn("force_replace_sources", js)
        self.assertIn("Replace anyway", js)
        app_src = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertEqual(app_src.count('force_replace_sources=force'), 2)


if __name__ == "__main__":
    unittest.main()
