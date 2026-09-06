import sqlite3
import tempfile
import unittest
from pathlib import Path

import dbcore
import sickchill_importer


def make_target(path: Path):
    with dbcore.connect(path) as c:
        c.executescript(
            """
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
            CREATE TABLE import_runs(
              id INTEGER PRIMARY KEY AUTOINCREMENT, source_name TEXT, shows_found INTEGER DEFAULT 0,
              shows_imported INTEGER DEFAULT 0, shows_skipped INTEGER DEFAULT 0,
              episodes_found INTEGER DEFAULT 0, episodes_imported INTEGER DEFAULT 0,
              episodes_skipped INTEGER DEFAULT 0, imported_at TEXT DEFAULT CURRENT_TIMESTAMP);
            """
        )


def make_sickchill(path: Path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE tv_shows(
          indexer_id INTEGER PRIMARY KEY,
          show_name TEXT,
          imdb_id TEXT,
          location TEXT,
          network TEXT,
          genre TEXT,
          quality TEXT,
          paused INTEGER,
          anime INTEGER,
          status TEXT
        );
        CREATE TABLE tv_episodes(
          showid INTEGER,
          season INTEGER,
          episode INTEGER,
          name TEXT,
          airdate TEXT,
          status TEXT,
          location TEXT,
          file_size INTEGER,
          release_name TEXT,
          quality TEXT
        );
        """
    )
    conn.execute("INSERT INTO tv_shows VALUES(?,?,?,?,?,?,?,?,?,?)", (12345, "Example Show", "123456", "D:/TV/Example Show", "NBC", "Drama", "HD", 0, 0, "Continuing"))
    conn.execute("INSERT INTO tv_episodes VALUES(?,?,?,?,?,?,?,?,?,?)", (12345, 1, 1, "Pilot", "2026-01-01", "Downloaded", "D:/TV/Example Show/S01E01.mkv", 100, "Example.Show.S01E01", "HD"))
    conn.execute("INSERT INTO tv_episodes VALUES(?,?,?,?,?,?,?,?,?,?)", (12345, 1, 2, "Second", "2026-01-08", "Wanted", "", 0, "", "HD"))
    conn.commit()
    conn.close()


class V17SickChillImporterTests(unittest.TestCase):
    def test_analyze_and_dry_run_do_not_write(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "sickbeard.db"
            dst = Path(td) / "tvmanager.db"
            make_sickchill(src)
            make_target(dst)
            analysis = sickchill_importer.analyze_database(src, dst)
            self.assertTrue(analysis["ready"])
            self.assertEqual(analysis["shows_found"], 1)
            self.assertEqual(analysis["episodes_found"], 2)
            self.assertEqual(analysis["sample_shows"][0]["imdb_id"], "tt0123456")

            preview = sickchill_importer.import_database(src, dst, "sickbeard.db", dry_run=True)
            self.assertTrue(preview["dry_run"])
            self.assertEqual(preview["shows_imported"], 1)
            with dbcore.connect(dst, wal=False, readonly=True) as c:
                self.assertEqual(c.execute("SELECT COUNT(*) FROM shows").fetchone()[0], 0)
                self.assertEqual(c.execute("SELECT COUNT(*) FROM episodes").fetchone()[0], 0)

    def test_import_is_idempotent_and_audited(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "sickbeard.db"
            dst = Path(td) / "tvmanager.db"
            make_sickchill(src)
            make_target(dst)
            first = sickchill_importer.import_database(src, dst, "sickbeard.db")
            self.assertEqual(first["shows_imported"], 1)
            self.assertEqual(first["episodes_imported"], 2)
            second = sickchill_importer.import_database(src, dst, "sickbeard.db")
            self.assertEqual(second["shows_imported"], 0)
            self.assertEqual(second["shows_skipped"], 1)
            self.assertEqual(second["episodes_skipped"], 2)
            with dbcore.connect(dst, wal=False, readonly=True) as c:
                self.assertEqual(c.execute("SELECT COUNT(*) FROM legacy_identity_map").fetchone()[0], 1)
                self.assertGreaterEqual(c.execute("SELECT COUNT(*) FROM import_run_details").fetchone()[0], 6)


if __name__ == "__main__":
    unittest.main()
