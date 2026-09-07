from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import import_recovery
import sickchill_importer
import dbcore

class ImportVisibilityTests(unittest.TestCase):
    def test_imported_sickchill_shows_are_visible_in_active_counts(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            source=base/'sickbeard.db'
            target=base/'tvmanager.db'
            with closing(sqlite3.connect(source)) as c, c:
                c.execute('CREATE TABLE tv_shows(indexer_id INTEGER, show_name TEXT, location TEXT, status TEXT)')
                c.execute('CREATE TABLE tv_episodes(showid INTEGER, season INTEGER, episode INTEGER, name TEXT)')
                c.execute('INSERT INTO tv_shows VALUES(?,?,?,?)',(12345,'Example Show','/tv/Example Show','Continuing'))
                c.execute('INSERT INTO tv_episodes VALUES(?,?,?,?)',(12345,1,1,'Pilot'))
            with dbcore.connect(target) as c:
                c.execute('CREATE TABLE shows(id INTEGER PRIMARY KEY AUTOINCREMENT, tmdb_id INTEGER UNIQUE, imdb_id TEXT, tvdb_id INTEGER, legacy_indexer_id INTEGER, name TEXT NOT NULL, original_name TEXT, first_air_date TEXT, overview TEXT, poster TEXT, vote_average REAL, location TEXT, network TEXT, genre TEXT, quality TEXT, paused INTEGER DEFAULT 0, anime INTEGER DEFAULT 0, status TEXT DEFAULT "Wanted", legacy_data TEXT, added_at TEXT DEFAULT CURRENT_TIMESTAMP)')
                c.execute('CREATE TABLE episodes(id INTEGER PRIMARY KEY AUTOINCREMENT, show_id INTEGER NOT NULL, season INTEGER NOT NULL, episode INTEGER NOT NULL, name TEXT, airdate TEXT, status TEXT, location TEXT, file_size INTEGER, release_name TEXT, quality TEXT, legacy_data TEXT, UNIQUE(show_id,season,episode))')
                c.execute('CREATE TABLE import_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, source_name TEXT, shows_found INTEGER DEFAULT 0, shows_imported INTEGER DEFAULT 0, shows_skipped INTEGER DEFAULT 0, episodes_found INTEGER DEFAULT 0, episodes_imported INTEGER DEFAULT 0, episodes_skipped INTEGER DEFAULT 0, imported_at TEXT DEFAULT CURRENT_TIMESTAMP)')
            stats=sickchill_importer.import_database(source,target,dry_run=False)
            counts=import_recovery.active_counts(target)
            self.assertEqual(stats['shows_imported'],1)
            self.assertEqual(counts['shows'],1)
            self.assertEqual(counts['episodes'],1)

    def test_recovery_rebuilds_empty_shows_from_import_audit(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'tvmanager.db'
            with dbcore.connect(target) as c:
                c.execute('CREATE TABLE shows(id INTEGER PRIMARY KEY AUTOINCREMENT, tmdb_id INTEGER UNIQUE, imdb_id TEXT, tvdb_id INTEGER, legacy_indexer_id INTEGER, name TEXT NOT NULL, original_name TEXT, first_air_date TEXT, overview TEXT, poster TEXT, vote_average REAL, location TEXT, network TEXT, genre TEXT, quality TEXT, paused INTEGER DEFAULT 0, anime INTEGER DEFAULT 0, status TEXT DEFAULT "Wanted", legacy_data TEXT, added_at TEXT DEFAULT CURRENT_TIMESTAMP)')
                c.execute('CREATE TABLE legacy_identity_map(source_name TEXT NOT NULL, legacy_show_id INTEGER, tvmanager_show_id INTEGER NOT NULL, tvdb_id INTEGER, imdb_id TEXT, show_name TEXT, imported_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(source_name, legacy_show_id))')
                c.execute('CREATE TABLE import_run_details(id INTEGER PRIMARY KEY AUTOINCREMENT, import_run_id INTEGER, source_name TEXT NOT NULL, item_type TEXT NOT NULL, source_id TEXT, tvmanager_id INTEGER, action TEXT NOT NULL, message TEXT, details_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
                details={'indexer_id': 77, 'show_name': 'Recovered Show', 'location': '/tv/Recovered Show', 'status': 'Continuing'}
                c.execute('INSERT INTO import_run_details(import_run_id,source_name,item_type,source_id,tvmanager_id,action,message,details_json) VALUES(?,?,?,?,?,?,?,?)',(1,'sickbeard.db','show','77',None,'imported','Recovered Show',json.dumps(details)))
            report=import_recovery.recover_shows_from_import_audit(target)
            counts=import_recovery.active_counts(target)
            self.assertTrue(report['attempted'])
            self.assertEqual(report['created'],1)
            self.assertEqual(counts['shows'],1)

if __name__ == '__main__':
    unittest.main()
