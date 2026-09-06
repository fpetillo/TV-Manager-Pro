import tempfile, unittest
from pathlib import Path
import dbcore, migrations

class MigrationTests(unittest.TestCase):
    def test_v16_migration(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/"tvmanager.db"
            with dbcore.connect(db) as c:
                c.executescript("""
                CREATE TABLE season_pack_downloads(
                    id INTEGER PRIMARY KEY, show_id INTEGER, season INTEGER,
                    search_id INTEGER, client TEXT, external_id TEXT,
                    title TEXT, status TEXT, created_at TEXT, completed_at TEXT
                );
                """)
                c.commit()
            result=migrations.migrate(db)
            self.assertEqual(result["quick_check"],"ok")
            with dbcore.connect(db) as c:
                self.assertIsNotNone(c.execute("SELECT 1 FROM schema_migrations WHERE version=16").fetchone())
                cols={r["name"] for r in c.execute("PRAGMA table_info(season_pack_downloads)")}
                self.assertTrue({"progress","error","updated_at"}.issubset(cols))
                subcols={r["name"] for r in c.execute("PRAGMA table_info(subtitle_jobs)")}
                self.assertTrue({"next_attempt_at","priority","provider"}.issubset(subcols))
                tables={r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertTrue({"media_fingerprints","scheduler_leases","admin_users","login_attempts","security_events","naming_presets","metadata_refresh_state"}.issubset(tables))
