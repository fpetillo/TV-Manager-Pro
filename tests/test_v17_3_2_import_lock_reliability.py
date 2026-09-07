import sqlite3
import tempfile
import unittest
from pathlib import Path

import dbcore
import sickchill_importer


def make_source(path: Path):
    with sqlite3.connect(path) as c:
        c.executescript('''
        CREATE TABLE tv_shows(indexer_id INTEGER PRIMARY KEY, show_name TEXT, imdb_id TEXT, location TEXT, status TEXT);
        CREATE TABLE tv_episodes(showid INTEGER, season INTEGER, episode INTEGER, name TEXT, status TEXT, location TEXT);
        ''')
        c.execute('INSERT INTO tv_shows VALUES(?,?,?,?,?)', (101, 'Lock Test Show', '7654321', '/tv/Lock Test Show', 'Continuing'))
        c.execute('INSERT INTO tv_episodes VALUES(?,?,?,?,?,?)', (101, 1, 1, 'Pilot', 'Downloaded', '/tv/Lock Test Show/S01E01.mkv'))


class ImportLockReliabilityTests(unittest.TestCase):
    def test_import_commits_closes_and_is_immediately_visible(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / 'sickbeard.db'
            dst = Path(td) / 'tvmanager.db'
            make_source(src)
            stats = sickchill_importer.import_database(src, dst, 'sickbeard.db')
            self.assertTrue(stats['committed'])
            self.assertEqual(stats['shows_imported'], 1)
            self.assertEqual(stats['episodes_imported'], 1)
            self.assertEqual(stats['target_visibility']['shows'], 1)
            self.assertEqual(stats['target_visibility']['episodes'], 1)
            # A brand-new writer can acquire the database immediately after import.
            with dbcore.connect(dst) as c:
                c.execute("INSERT INTO settings(section,name,value) VALUES('test','post_import_write','ok')")
            with dbcore.connect(dst, wal=False, readonly=True) as c:
                self.assertEqual(c.execute('SELECT COUNT(*) FROM shows').fetchone()[0], 1)
                self.assertEqual(c.execute("SELECT value FROM settings WHERE section='test' AND name='post_import_write'").fetchone()[0], 'ok')

    def test_dry_run_leaves_no_target_rows_and_no_lock(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / 'sickbeard.db'
            dst = Path(td) / 'tvmanager.db'
            make_source(src)
            stats = sickchill_importer.import_database(src, dst, 'sickbeard.db', dry_run=True)
            self.assertTrue(stats['dry_run'])
            with dbcore.connect(dst) as c:
                c.execute("INSERT INTO settings(section,name,value) VALUES('test','after_dry_run','ok')")
                self.assertEqual(c.execute('SELECT COUNT(*) FROM shows').fetchone()[0], 0)

if __name__ == '__main__':
    unittest.main()
