import tempfile, unittest
from pathlib import Path
import advanced, ops, intelligence, completion, production, release, sync, engine, lifecycle, migrations, dbcore, security, metadata_service

class StartupSchemaTests(unittest.TestCase):
    def test_full_module_initialization_on_new_database(self):
        modules=[advanced,ops,intelligence,completion,production,release,sync,engine,lifecycle,security,metadata_service]
        originals={m:getattr(m,"DB",None) for m in modules}
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/"tvmanager.db"
            try:
                for m in modules:
                    if hasattr(m,"DB"):m.DB=db
                with dbcore.connect(db) as c:
                    c.executescript("""
                    CREATE TABLE shows(
                      id INTEGER PRIMARY KEY AUTOINCREMENT, tmdb_id INTEGER UNIQUE, imdb_id TEXT,
                      tvdb_id INTEGER, legacy_indexer_id INTEGER, name TEXT NOT NULL, original_name TEXT,
                      first_air_date TEXT, overview TEXT, poster TEXT, vote_average REAL, location TEXT,
                      network TEXT, genre TEXT, quality TEXT, paused INTEGER DEFAULT 0, anime INTEGER DEFAULT 0,
                      status TEXT DEFAULT 'Wanted', legacy_data TEXT, added_at TEXT DEFAULT CURRENT_TIMESTAMP);
                    CREATE TABLE episodes(
                      id INTEGER PRIMARY KEY AUTOINCREMENT, show_id INTEGER NOT NULL, season INTEGER NOT NULL,
                      episode INTEGER NOT NULL, name TEXT, airdate TEXT, status TEXT, location TEXT,
                      file_size INTEGER, release_name TEXT, quality TEXT, legacy_data TEXT,
                      UNIQUE(show_id,season,episode));
                    CREATE TABLE settings(
                      section TEXT NOT NULL,name TEXT NOT NULL,value TEXT,is_secret INTEGER NOT NULL DEFAULT 0,
                      source TEXT NOT NULL DEFAULT 'app',updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                      PRIMARY KEY(section,name));
                    """)
                engine.init_engine()
                migrations.migrate(db)
                lifecycle.init()
                security.init()
                metadata_service.init()
                with dbcore.connect(db) as c:
                    expected={
                        "downloads","season_pack_downloads","subtitle_jobs","media_servers",
                        "schema_migrations","acquisition_events","upgrade_replacements",
                        "scheduler_runs","acquisition_episode_links","media_fingerprints","scheduler_leases","admin_users","login_attempts","security_events","metadata_refresh_state"
                    }
                    tables={r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    self.assertTrue(expected.issubset(tables),expected-tables)
                    self.assertEqual(c.execute("PRAGMA quick_check").fetchone()[0],"ok")
                self.assertEqual(lifecycle.unified_queue(),[])
            finally:
                for m,v in originals.items():
                    if v is not None:m.DB=v
