import tempfile
import unittest
from pathlib import Path

import dbcore
import library_maintenance


class V1712LibraryHealthFixTests(unittest.TestCase):
    def test_health_report_survives_legacy_minimal_schema(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "legacy.db"
            with dbcore.connect(db) as c:
                c.executescript(
                    """
                    CREATE TABLE shows(id INTEGER PRIMARY KEY, name TEXT);
                    CREATE TABLE episodes(id INTEGER PRIMARY KEY, show_id INTEGER, season INTEGER, episode INTEGER);
                    CREATE TABLE media_fingerprints(path TEXT, file_size INTEGER, fingerprint TEXT);
                    INSERT INTO shows VALUES(1,'Legacy Show');
                    INSERT INTO episodes VALUES(1,1,1,1);
                    INSERT INTO media_fingerprints VALUES('/tmp/a.mkv',100,'same');
                    INSERT INTO media_fingerprints VALUES('/tmp/b.mkv',100,'same');
                    """
                )
            report = library_maintenance.library_health_report(db)
            self.assertTrue(report["ok"])
            self.assertEqual(report["counts"]["shows"], 1)
            self.assertEqual(report["counts"]["episodes"], 1)
            self.assertEqual(report["counts"]["duplicate_groups"], 1)
            self.assertTrue(report["schema_warnings"])

    def test_missing_on_disk_is_separate_from_empty_location(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "tvmanager.db"
            existing = root / "existing.mkv"
            existing.write_text("ok", encoding="utf-8")
            missing = root / "missing.mkv"
            with dbcore.connect(db) as c:
                c.executescript(
                    """
                    CREATE TABLE shows(id INTEGER PRIMARY KEY, name TEXT, imdb_id TEXT, tmdb_id INTEGER, tvdb_id INTEGER, location TEXT);
                    CREATE TABLE episodes(id INTEGER PRIMARY KEY, show_id INTEGER, season INTEGER, episode INTEGER, name TEXT, status TEXT, location TEXT);
                    """
                )
                c.execute("INSERT INTO shows VALUES(1,'Example','tt1',1,1,?)", (str(root),))
                c.execute("INSERT INTO episodes VALUES(1,1,1,1,'Existing','Downloaded',?)", (str(existing),))
                c.execute("INSERT INTO episodes VALUES(2,1,1,2,'Missing','Downloaded',?)", (str(missing),))
                c.execute("INSERT INTO episodes VALUES(3,1,1,3,'Wanted','Wanted','')")
            report = library_maintenance.library_health_report(db)
            self.assertEqual(report["counts"]["downloaded_episodes"], 2)
            self.assertEqual(report["counts"]["missing_episode_files"], 1)
            self.assertEqual(report["counts"]["episodes_without_file_location"], 1)
            self.assertEqual(report["samples"]["missing_episode_files"][0]["location"], str(missing))

    def test_library_health_frontend_has_error_status_and_cache_buster(self):
        html = Path("templates/library_health.html").read_text(encoding="utf-8")
        js = Path("static/library_health.js").read_text(encoding="utf-8")
        self.assertIn('id="healthStatus"', html)
        self.assertIn('library_health.js?v={{ app_version }}', html)
        self.assertIn('Library Health could not load', js)
        self.assertIn('episodesWithoutFiles', js)


if __name__ == "__main__":
    unittest.main()
