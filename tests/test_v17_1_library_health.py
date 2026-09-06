import tempfile
import unittest
from pathlib import Path

import dbcore
import library_maintenance


class V171LibraryHealthTests(unittest.TestCase):
    def make_db(self, db: Path):
        with dbcore.connect(db) as c:
            c.executescript(
                """
                CREATE TABLE shows(id INTEGER PRIMARY KEY, name TEXT, imdb_id TEXT, tmdb_id INTEGER, tvdb_id INTEGER, location TEXT);
                CREATE TABLE episodes(id INTEGER PRIMARY KEY, show_id INTEGER, season INTEGER, episode INTEGER, name TEXT, status TEXT, location TEXT);
                CREATE TABLE metadata_refresh_state(show_id INTEGER PRIMARY KEY,last_refresh TEXT,last_status TEXT,last_error TEXT,updated_at TEXT);
                CREATE TABLE media_fingerprints(path TEXT PRIMARY KEY,file_size INTEGER NOT NULL,mtime_ns INTEGER,fingerprint TEXT NOT NULL,episode_id INTEGER,checked_at TEXT DEFAULT CURRENT_TIMESTAMP);
                INSERT INTO shows VALUES(1,'Example Show',NULL,NULL,NULL,'');
                INSERT INTO episodes VALUES(10,1,1,1,'Pilot','Wanted','');
                INSERT INTO episodes VALUES(11,1,1,2,'Second','Downloaded','/tmp/second.mkv');
                INSERT INTO media_fingerprints(path,file_size,fingerprint,episode_id) VALUES('/tmp/a.mkv',100,'abc',10);
                INSERT INTO media_fingerprints(path,file_size,fingerprint,episode_id) VALUES('/tmp/b.mkv',100,'abc',10);
                """
            )

    def test_health_report_counts_common_import_problems(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "tvmanager.db"
            self.make_db(db)
            report = library_maintenance.library_health_report(db)
            self.assertEqual(report["counts"]["shows"], 1)
            self.assertEqual(report["counts"]["missing_episode_files"], 1)
            self.assertEqual(report["counts"]["shows_missing_external_ids"], 1)
            self.assertEqual(report["counts"]["duplicate_groups"], 1)
            self.assertTrue(report["recommendations"])

    def test_duplicate_cleanup_preview_and_apply_moves_to_managed_trash(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "tvmanager.db"
            self.make_db(db)
            a = root / "a.mkv"
            b = root / "b.mkv"
            a.write_text("same")
            b.write_text("same")
            with dbcore.connect(db) as c:
                c.execute("UPDATE media_fingerprints SET path=? WHERE path='/tmp/a.mkv'", (str(a),))
                c.execute("UPDATE media_fingerprints SET path=? WHERE path='/tmp/b.mkv'", (str(b),))
            preview = library_maintenance.duplicate_cleanup_preview(db, keep_path=str(a))
            self.assertEqual(preview["action_count"], 1)
            self.assertEqual(preview["actions"][0]["source_path"], str(b))
            applied = library_maintenance.apply_duplicate_cleanup(db, trash_root=root / "managed_trash", actions=preview["actions"])
            self.assertEqual(applied["moved"], 1)
            self.assertTrue(a.exists())
            self.assertFalse(b.exists())
            with dbcore.connect(db, wal=False, readonly=True) as c:
                self.assertEqual(c.execute("SELECT COUNT(*) FROM duplicate_cleanup_actions").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
