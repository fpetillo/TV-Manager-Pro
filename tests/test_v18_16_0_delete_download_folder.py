"""v18.16.0: optional removal of the download folder after its episodes are moved."""
import json, os, shutil, subprocess, sys, tempfile, textwrap, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCENARIO = textwrap.dedent(r'''
    import json, sys
    from pathlib import Path
    import app, engine
    lib = Path(sys.argv[1]); dl = Path(sys.argv[2]); setting = sys.argv[3]; method = sys.argv[4]
    show_dir = lib / "Good Show"; show_dir.mkdir(parents=True)
    with engine.cx() as c:
        c.execute("INSERT INTO shows(id,name,location,season_folders) VALUES(7,'Good Show',?,1)", (str(show_dir),))
        for n in (1, 2, 3, 4):
            c.execute("INSERT INTO episodes(show_id,season,episode,name,status) VALUES(7,1,?,?,'Wanted')", (n, f"Ep{n}"))
        c.commit()
    engine.set_setting("General", "delete_source_folder", setting)
    engine.set_setting("TVManager", "refresh_media_servers_after_process", "0")
    # Folder A: one episode plus leftovers, including a sample video in a Sample subfolder.
    a = dl / "Good.Show.S01E01.1080p.WEB-DL-GRP"; (a / "Sample").mkdir(parents=True)
    (a / "Good.Show.S01E01.1080p.WEB-DL-GRP.mkv").write_text("E1")
    (a / "Good.Show.S01E01.1080p.WEB-DL-GRP.nfo").write_text("nfo")
    (a / "readme.txt").write_text("txt")
    (a / "Sample" / "good.show.s01e01.sample.mkv").write_text("sample")
    # Folder B: two episodes, only one selected, so it must be kept.
    b = dl / "Good.Show.S01E02-E03.Pack"; b.mkdir()
    (b / "Good.Show.S01E02.1080p.WEB-DL.mkv").write_text("E2")
    (b / "Good.Show.S01E03.1080p.WEB-DL.mkv").write_text("E3")
    # File directly in the downloads folder: no folder to remove, root must survive.
    (dl / "Good.Show.S01E04.1080p.WEB-DL.mkv").write_text("E4")
    selected = [str(a / "Good.Show.S01E01.1080p.WEB-DL-GRP.mkv"), str(b / "Good.Show.S01E02.1080p.WEB-DL.mkv"), str(dl / "Good.Show.S01E04.1080p.WEB-DL.mkv")]
    run = engine.scan_postprocess(dry_run=False, root_override=str(dl), selected_sources=selected, process_method_override=method)
    print(json.dumps({"processed": run.get("processed_count"), "errors": run.get("errors"),
                      "removed": run.get("removed_folders"), "kept": run.get("kept_folders"),
                      "a_exists": a.exists(), "b_exists": b.exists(), "root_exists": dl.exists(),
                      "library": sorted(str(p.relative_to(show_dir)) for p in show_dir.rglob("*") if p.is_file())}))
''')


def run_scenario(setting, method="move"):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp); code = tmp / "app"
        shutil.copytree(ROOT, code, ignore=shutil.ignore_patterns(".git", "tests", "*.db*", "managed_trash", "logs", ".runtime", "__pycache__", "imports", "backups"))
        (code / "scenario.py").write_text(SCENARIO, encoding="utf-8")
        lib, dl = tmp / "library", tmp / "downloads"; lib.mkdir(); dl.mkdir()
        out = subprocess.run([sys.executable, "scenario.py", str(lib), str(dl), setting, method], cwd=code,
                             capture_output=True, text=True, timeout=180, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if out.returncode != 0:
            raise AssertionError(out.stderr[-3000:])
        return json.loads(out.stdout.strip().splitlines()[-1])


class DeleteDownloadFolderTests(unittest.TestCase):
    def test_enabled_removes_finished_folder_and_keeps_the_rest(self):
        r = run_scenario("1")
        self.assertEqual(r["processed"], 3, r)
        self.assertFalse(r["errors"], r["errors"])
        self.assertFalse(r["a_exists"], "finished release folder with leftovers should be removed")
        self.assertTrue(r["b_exists"], "folder with an unprocessed episode must be kept")
        self.assertTrue(r["root_exists"], "the completed-downloads folder itself is never removed")
        self.assertEqual(len(r["removed"]), 1)
        self.assertEqual(r["removed"][0]["leftover_files"], 2)  # readme.txt and the sample; the .nfo moved with the episode
        self.assertIn("not processed", r["kept"][0]["reason"])
        self.assertEqual(len(r["library"]), 3 + 1)  # three episodes plus the moved .nfo sidecar

    def test_disabled_by_default_behaviour(self):
        r = run_scenario("0")
        self.assertEqual(r["processed"], 3, r)
        self.assertTrue(r["a_exists"]); self.assertTrue(r["b_exists"])
        self.assertFalse(r["removed"])

    def test_only_applies_to_move(self):
        r = run_scenario("1", "copy")
        self.assertEqual(r["processed"], 3, r)
        self.assertTrue(r["a_exists"]); self.assertFalse(r["removed"])

    def test_setting_is_configurable(self):
        import configuration
        self.assertEqual(configuration.validate("General", "delete_source_folder", "on"), "1")
        defaults = json.loads((ROOT / "settings_defaults.json").read_text(encoding="utf-8"))
        self.assertEqual(defaults["General"]["delete_source_folder"], "0")
        self.assertIn('"delete_source_folder"', (ROOT / "app.py").read_text(encoding="utf-8"))
        self.assertIn("deleteSourceFolder", (ROOT / "templates" / "postprocess.html").read_text(encoding="utf-8"))
        self.assertIn("delete_source_folder", (ROOT / "static" / "postprocess.js").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
