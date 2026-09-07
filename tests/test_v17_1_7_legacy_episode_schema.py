import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class LegacyEpisodeSchemaRepairTests(unittest.TestCase):
    def test_init_repairs_episode_status_before_normalize_statuses(self):
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        ensure_pos = app_source.index('_ensure_columns(c, "episodes", {')
        normalize_pos = app_source.index('engine.normalize_statuses()')
        ensure_block = app_source[ensure_pos:normalize_pos]
        self.assertIn('"status": "TEXT DEFAULT \'Wanted\'"', ensure_block)
        self.assertIn('"location": "TEXT"', ensure_block)
        self.assertLess(ensure_pos, normalize_pos)

    def test_legacy_episode_table_can_be_repaired_by_same_columns(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "tvmanager.db"
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            conn.execute("CREATE TABLE shows(id INTEGER PRIMARY KEY AUTOINCREMENT, tmdb_id INTEGER UNIQUE, name TEXT NOT NULL)")
            conn.execute("CREATE TABLE episodes(id INTEGER PRIMARY KEY AUTOINCREMENT, show_id INTEGER NOT NULL, season INTEGER NOT NULL, episode INTEGER NOT NULL, UNIQUE(show_id,season,episode))")
            conn.execute("INSERT INTO shows(name) VALUES('Legacy Show')")
            conn.execute("INSERT INTO episodes(show_id,season,episode) VALUES(1,1,1)")
            before = {r['name'] for r in conn.execute('PRAGMA table_info(episodes)').fetchall()}
            self.assertNotIn('status', before)
            for name, definition in {
                "name": "TEXT",
                "airdate": "TEXT",
                "status": "TEXT DEFAULT 'Wanted'",
                "location": "TEXT",
                "file_size": "INTEGER",
                "release_name": "TEXT",
                "quality": "TEXT",
                "legacy_data": "TEXT",
            }.items():
                if name not in before:
                    conn.execute(f'ALTER TABLE episodes ADD COLUMN "{name}" {definition}')
            row = conn.execute("SELECT id,status,location FROM episodes").fetchone()
            self.assertEqual(row['status'], 'Wanted')
            self.assertIsNone(row['location'])
            conn.close()

    def test_version_is_17_1_7(self):
        self.assertIn((ROOT / 'VERSION').read_text(encoding='utf-8').strip(), {'17.1.8','17.1.9','17.2.0', '17.3.0', '17.3.1', '17.3.2', '17.3.3', '17.3.4', '17.3.5', '17.4.0', '17.5.0', '17.6.0', '17.6.1', '17.7.0', '17.9.0', '17.10.0', '17.11.0', '17.12.0', '17.13.0', '17.13.1', '17.13.2', '17.13.3', '17.14.0', '17.15.0', '17.16.0', '17.18.0', "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3"})

if __name__ == '__main__':
    unittest.main()
