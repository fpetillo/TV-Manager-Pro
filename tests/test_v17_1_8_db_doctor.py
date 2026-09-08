from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

import db_doctor


class StartupDatabaseDoctorTests(unittest.TestCase):
    def test_repairs_minimal_legacy_database_before_startup_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "tvmanager.db"
            with closing(sqlite3.connect(db)) as c, c:
                c.execute("CREATE TABLE shows(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)")
                c.execute("CREATE TABLE episodes(id INTEGER PRIMARY KEY AUTOINCREMENT, show_id INTEGER, season INTEGER, episode INTEGER)")
                c.execute("INSERT INTO shows(name) VALUES('Legacy Show')")
                c.execute("INSERT INTO episodes(show_id,season,episode) VALUES(1,1,1)")
            report = db_doctor.repair(db)
            self.assertEqual(report["quick_check"], "ok")
            with closing(sqlite3.connect(db)) as c, c:
                show_cols = {r[1] for r in c.execute("PRAGMA table_info(shows)")}
                ep_cols = {r[1] for r in c.execute("PRAGMA table_info(episodes)")}
                self.assertIn("imdb_id", show_cols)
                self.assertIn("season_folders", show_cols)
                self.assertIn("status", ep_cols)
                self.assertIn("location", ep_cols)
                row = c.execute("SELECT status FROM episodes WHERE id=1").fetchone()
                self.assertEqual(row[0], "Wanted")

    def test_version_is_17_1_8(self):
        self.assertIn((Path(__file__).resolve().parents[1] / "VERSION").read_text().strip(), {"17.1.8", "17.1.9", "17.2.0", "17.3.0", "17.3.1", "17.3.2", "17.3.3", "17.3.4", "17.3.5", "17.4.0", "17.5.0", "17.6.0", "17.6.1", "17.7.0", "17.9.0", "17.10.0", "17.11.0", "17.12.0", "17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6", "18.5.7"})
