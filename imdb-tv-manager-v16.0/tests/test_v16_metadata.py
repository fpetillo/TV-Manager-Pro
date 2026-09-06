import tempfile, unittest
from pathlib import Path
import metadata_service, dbcore

class MetadataServiceTests(unittest.TestCase):
    def test_init_and_empty_batch(self):
        old=metadata_service.DB
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/"tvmanager.db"
            metadata_service.DB=db
            try:
                with dbcore.connect(db) as c:
                    c.executescript("""
                    CREATE TABLE settings(
                      section TEXT NOT NULL,name TEXT NOT NULL,value TEXT,is_secret INTEGER DEFAULT 0,
                      source TEXT DEFAULT 'app',updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                      PRIMARY KEY(section,name));
                    CREATE TABLE shows(
                      id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,paused INTEGER DEFAULT 0,
                      metadata_enabled INTEGER DEFAULT 1,tmdb_id INTEGER,imdb_id TEXT,tvdb_id INTEGER);
                    """)
                metadata_service.init()
                result=metadata_service.refresh_batch(limit=3)
                self.assertEqual(result["eligible_selected"],0)
                with dbcore.connect(db) as c:
                    self.assertIsNotNone(c.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='metadata_refresh_state'"
                    ).fetchone())
            finally:
                metadata_service.DB=old
