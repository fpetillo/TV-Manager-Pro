import tempfile
import unittest
from pathlib import Path

import dbcore
import library_maintenance


class V17LibraryMaintenanceTests(unittest.TestCase):
    def test_duplicate_candidates_from_fingerprint_cache(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "tvmanager.db"
            with dbcore.connect(db) as c:
                c.executescript(
                    """
                    CREATE TABLE shows(id INTEGER PRIMARY KEY, name TEXT);
                    CREATE TABLE episodes(id INTEGER PRIMARY KEY, show_id INTEGER, season INTEGER, episode INTEGER);
                    CREATE TABLE media_fingerprints(path TEXT PRIMARY KEY,file_size INTEGER NOT NULL,mtime_ns INTEGER,fingerprint TEXT NOT NULL,episode_id INTEGER,checked_at TEXT DEFAULT CURRENT_TIMESTAMP);
                    INSERT INTO shows VALUES(1,'Example Show');
                    INSERT INTO episodes VALUES(10,1,1,1);
                    INSERT INTO media_fingerprints(path,file_size,fingerprint,episode_id) VALUES('/a.mkv',100,'abc',10);
                    INSERT INTO media_fingerprints(path,file_size,fingerprint,episode_id) VALUES('/b.mkv',100,'abc',10);
                    INSERT INTO media_fingerprints(path,file_size,fingerprint,episode_id) VALUES('/c.mkv',200,'def',10);
                    """
                )
            results = library_maintenance.duplicate_candidates(db)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["duplicate_count"], 2)
            self.assertEqual(results[0]["safe_action"], "review")


if __name__ == "__main__":
    unittest.main()
