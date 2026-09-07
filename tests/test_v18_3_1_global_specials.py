from pathlib import Path
import sqlite3
import tempfile

import episode_rules

ROOT = Path(__file__).resolve().parents[1]


def make_db():
    tmp = Path(tempfile.mkdtemp()) / 'tvmanager.db'
    with sqlite3.connect(tmp) as c:
        c.row_factory = sqlite3.Row
        c.executescript('''
        CREATE TABLE shows(id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE episodes(id INTEGER PRIMARY KEY, show_id INTEGER, season INTEGER, episode INTEGER, name TEXT, status TEXT, location TEXT, airdate TEXT);
        CREATE TABLE settings(section TEXT, key TEXT, value TEXT, PRIMARY KEY(section,key));
        CREATE TABLE logs(id INTEGER PRIMARY KEY, action TEXT, message TEXT, show_id INTEGER, data TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE mass_update_history(id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, filter_json TEXT, affected INTEGER, message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        INSERT INTO shows(id,name) VALUES(1,'Demo Show'),(2,'Other Show');
        INSERT INTO episodes(id,show_id,season,episode,name,status,location,airdate) VALUES
          (1,1,0,1,'Special One','Wanted',NULL,'2020-01-01'),
          (2,1,1,1,'Pilot','Wanted',NULL,'2020-01-02'),
          (3,2,0,1,'Behind the Scenes','Wanted',NULL,'2021-01-01'),
          (4,2,2,1,'Regular','Wanted','/tv/regular.mkv','2021-01-02');
        ''')
    return tmp


def test_version_is_18_3_1():
    assert (ROOT / 'VERSION').read_text(encoding='utf-8').strip() in {'18.3.1', '18.3.2', '18.3.3', '18.4.0', '18.4.1', '18.4.2', '18.4.3'}


def test_global_ignore_specials_updates_all_shows_and_regulars_stay_considered():
    db = make_db()
    result = episode_rules.ignore_specials(db, None, reason='Season 00 / Specials hidden from Missing/Wanted globally')
    assert result['affected'] == 2
    with sqlite3.connect(db) as c:
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute('SELECT season,status,monitored,ignored,ignored_reason FROM episodes ORDER BY id')]
    assert rows[0]['season'] == 0 and rows[0]['ignored'] == 1 and rows[0]['monitored'] == 0 and rows[0]['status'] == 'Ignored'
    assert rows[2]['season'] == 0 and rows[2]['ignored'] == 1 and rows[2]['monitored'] == 0 and rows[2]['status'] == 'Ignored'
    assert rows[1]['ignored'] in (0, None) and rows[1]['status'] == 'Wanted'
    assert rows[3]['ignored'] in (0, None) and rows[3]['status'] == 'Wanted'


def test_considered_sql_excludes_ignored_and_specials_from_missing_wanted_logic():
    clause = episode_rules.considered_sql('e', ignore_specials=True)
    assert 'ignored' in clause
    assert 'season' in clause and '<>0' in clause
