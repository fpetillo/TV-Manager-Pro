from contextlib import closing
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

import sickchill_importer


class ImportProgressTests(unittest.TestCase):
    def test_progress_callback_reaches_complete(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / 'sickbeard.db'
            dst = td / 'tvmanager.db'
            with closing(sqlite3.connect(src)) as c, c:
                c.executescript('''
                CREATE TABLE tv_shows(indexer_id INTEGER, show_name TEXT, imdb_id TEXT, location TEXT, status TEXT);
                CREATE TABLE tv_episodes(showid INTEGER, season INTEGER, episode INTEGER, name TEXT, location TEXT, status TEXT);
                INSERT INTO tv_shows VALUES(100, 'Example Show', '12345', '/tv/Example Show', 'Continuing');
                INSERT INTO tv_episodes VALUES(100, 1, 1, 'Pilot', '/tv/Example Show/S01E01.mkv', 'Downloaded');
                ''')
            events=[]
            result=sickchill_importer.import_database(src,dst,'sickbeard.db',progress_callback=lambda e: events.append(dict(e)))
            self.assertTrue(result['committed'])
            self.assertEqual(events[-1]['stage'], 'complete')
            self.assertEqual(events[-1]['percent'], 100)
            self.assertTrue(any(e['stage']=='shows' for e in events))
            self.assertTrue(any(e['stage']=='episodes' for e in events))

    def test_import_job_routes_exist(self):
        app_py = Path(__file__).resolve().parents[1] / 'app.py'
        src = app_py.read_text(encoding='utf-8')
        self.assertIn('@app.post("/api/import/sickchill/jobs")', src)
        self.assertIn('@app.get("/api/import/sickchill/jobs/<job_id>")', src)

    def test_import_center_contains_progress_bar(self):
        root = Path(__file__).resolve().parents[1]
        html = (root/'templates'/'import.html').read_text(encoding='utf-8')
        js = (root/'static'/'import.js').read_text(encoding='utf-8')
        self.assertIn('importProgress', html)
        self.assertIn('/api/import/sickchill/jobs', js)
        self.assertIn('pollImportJob', js)

if __name__ == '__main__':
    unittest.main()
