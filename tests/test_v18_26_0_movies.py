"""v18.26.0: Movies — discovery, search, handoff, polling, import and library scan."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import dbcore  # noqa: E402
import engine  # noqa: E402
import indexer_client  # noqa: E402
import movies  # noqa: E402


@pytest.fixture
def db(tmp_path, monkeypatch):
    database = tmp_path / 'movies.db'
    monkeypatch.setattr(engine, 'DB', database)
    with dbcore.connect(database) as c:
        c.executescript('''
        CREATE TABLE settings(section TEXT,name TEXT,value TEXT,is_secret INTEGER,source TEXT,updated_at TEXT,UNIQUE(section,name));
        CREATE TABLE scheduler_jobs(name TEXT PRIMARY KEY,enabled INTEGER,interval_minutes INTEGER,last_run TEXT,next_run TEXT,last_status TEXT,last_message TEXT);
        CREATE TABLE failed_releases(guid TEXT);
        ''')
    movies.init()
    logs = []
    monkeypatch.setattr(engine, 'log', lambda *a, **k: logs.append(a))
    monkeypatch.setattr(movies, '_sab_complete_dirs', lambda: [])
    library = tmp_path / 'Movies'
    library.mkdir()
    downloads = tmp_path / 'complete'
    downloads.mkdir()
    engine.set_setting('Movies', 'library_root', str(library))
    engine.set_setting('Movies', 'download_dir', str(downloads))
    engine.set_setting('Movies', 'library_scanned_at', '2026-01-01T00:00:00')
    engine.set_setting('General', 'nzb_method', 'sabnzbd')
    engine.set_setting('General', 'torrent_method', 'utorrent')
    import advanced
    monkeypatch.setattr(advanced, 'media_servers', lambda: [])
    monkeypatch.setattr(advanced, 'fire_webhooks', lambda *a, **k: None)
    import ops
    monkeypatch.setattr(ops, 'provider_is_available', lambda name: True)
    monkeypatch.setattr(ops, 'provider_result', lambda *a, **k: None)
    return SimpleNamespace(path=database, library=library, downloads=downloads, logs=logs)


def add(title='Dune Part Two', year=2024, **extra):
    with engine.cx() as c:
        cur = c.execute("INSERT INTO movies(tmdb_id,imdb_id,title,year,status,monitored,release_date,available_date) VALUES(?,?,?,?,?,1,?,?)",
                        (extra.get('tmdb_id', 693134), extra.get('imdb_id', 'tt15239678'), title, year, extra.get('status', 'Wanted'),
                         f'{year}-03-01', extra.get('available_date', f'{year}-05-01')))
        c.commit()
        return cur.lastrowid


def feed(*items):
    body = ''.join(f'<item><title>{t}</title><guid>{g}</guid><enclosure url="https://idx.test/{g}" length="{s}"/>'
                   f'<newznab:attr xmlns:newznab="http://www.newznab.com/DTD/2010/feeds/attributes/" name="seeders" value="{seed}"/></item>'
                   for t, g, s, seed in items)
    return ET.fromstring(f'<rss><channel>{body}</channel></rss>')


GB = 1024 ** 3


# ---------------------------------------------------------------- matching

@pytest.mark.parametrize('release,movie,ok', [
    ('Dune.Part.Two.2024.1080p.WEB-DL.DDP5.1.H.264-GROUP', {'title': 'Dune: Part Two', 'year': 2024}, True),
    ('Dune.2021.1080p.BluRay.x264', {'title': 'Dune: Part Two', 'year': 2024}, False),
    ('Batman.2022.1080p.WEB', {'title': 'The Batman', 'year': 2022}, True),
    ('Fast.and.Furious.2009.720p.BluRay', {'title': 'Fast & Furious', 'year': 2009}, True),
    ('Blade.Runner.2049.2017.2160p.UHD.BluRay', {'title': 'Blade Runner 2049', 'year': 2017}, True),
    ('1917.2019.1080p.BluRay', {'title': '1917', 'year': 2019}, True),
    ('Dune.Part.Two.2023.1080p.WEB', {'title': 'Dune: Part Two', 'year': 2024}, True),   # off by one year is accepted
    ('Dune.Part.Two.2020.1080p.WEB', {'title': 'Dune: Part Two', 'year': 2024}, False),
    ('Dune.Part.Two.1080p.WEB', {'title': 'Dune: Part Two', 'year': 2024}, False),        # no year
    ('Silo.S02E01.1080p.WEB', {'title': 'Silo', 'year': 2023}, False),
    ('Up.2009.1080p.BluRay', {'title': 'Upgrade', 'year': 2018}, False),
])
def test_release_matching(release, movie, ok):
    assert (movies.release_rejection(release, movie) is None) is ok


def test_scoring_rejects_bad_copies_and_prefers_better_quality(db):
    movie = {'title': 'Dune: Part Two', 'year': 2024}

    def score(title, size=8 * GB, **extra):
        return movies.score_release(dict({'title': title, 'size': size, 'protocol': 'nzb'}, **extra), movie)
    assert 'camera' in score('Dune.Part.Two.2024.HDCAM.x264')[1]
    assert 'Above maximum' in score('Dune.Part.Two.2024.2160p.WEB-DL')[1]
    assert 'Below minimum' in score('Dune.Part.Two.2024.480p.WEB')[1]
    assert 'Remux' in score('Dune.Part.Two.2024.1080p.BluRay.REMUX')[1]
    assert 'Smaller' in score('Dune.Part.Two.2024.1080p.WEB', size=100 * 1024 * 1024)[1]
    assert 'Larger' in score('Dune.Part.Two.2024.1080p.BluRay', size=60 * GB)[1]
    assert 'seeders' in score('Dune.Part.Two.2024.1080p.BluRay', protocol='torrent', seeders=0)[1]
    assert 'Disc image' in score('Dune.Part.Two.2024.1080p.COMPLETE.BLURAY.ISO')[1]
    bluray, web720 = score('Dune.Part.Two.2024.1080p.BluRay.x264')[0], score('Dune.Part.Two.2024.720p.WEB-DL')[0]
    assert bluray > web720
    engine.set_setting('Movies', 'max_resolution', '2160')
    assert score('Dune.Part.Two.2024.2160p.WEB-DL')[1] is None
    engine.set_setting('General', 'ignore_words', 'hardcoded')
    assert 'Ignored word' in score('Dune.Part.Two.2024.1080p.WEB.HARDCODED')[1]


# ---------------------------------------------------------------- search + grab

def test_search_by_imdb_grabs_best_and_records_download(db, monkeypatch):
    mid = add()
    provider = {'name': 'Geek', 'url': 'https://idx.test', 'api_key': 'k', 'protocol': 'nzb', 'priority': 0}
    monkeypatch.setattr(movies, 'providers', lambda: [provider])
    movies._movie_mode_unsupported.clear()
    calls = []

    def request_xml(p, params, timeout):
        calls.append(params)
        return feed(('Dune.Part.Two.2024.720p.WEB-DL', 'g1', 3 * GB, 0),
                    ('Dune.Part.Two.2024.1080p.BluRay.x264', 'g2', 10 * GB, 0),
                    ('Dune.Part.Two.2024.HDCAM', 'g3', 2 * GB, 0),
                    ('Dune.2021.1080p.BluRay', 'g4', 9 * GB, 0))
    monkeypatch.setattr(indexer_client, 'request_xml', request_xml)
    sent = []
    monkeypatch.setattr(movies, '_send_sab', lambda r: sent.append(r['title']) or 'SABnzbd_nzo_1')
    out = movies.search_movie(mid, auto_grab=True)
    assert calls[0]['t'] == 'movie' and calls[0]['imdbid'] == '15239678' and calls[0]['cat'] == '2000'
    assert len(calls) == 1  # the ID search found results, so no text search
    assert sent == ['Dune.Part.Two.2024.1080p.BluRay.x264']
    assert out['grabbed']['client'] == 'SABnzbd'
    assert [r['rejected_reason'] is None for r in out['results']] == [True, True, False, False]
    movie = movies.get_movie(mid)
    assert movie['status'] == 'Snatched' and movie['search_count'] == 1
    with engine.cx() as c:
        d = dict(c.execute('SELECT * FROM movie_downloads').fetchone())
    assert d['external_id'] == 'SABnzbd_nzo_1' and d['status'] == 'Queued' and d['guid'] == 'g2'
    with pytest.raises(ValueError, match='active download'):
        movies.grab_result(out['results'][1]['id'])


def test_text_search_fallback_and_blocklist(db, monkeypatch):
    mid = add()
    monkeypatch.setattr(movies, 'providers', lambda: [{'name': 'NoMovie', 'url': 'https://nomovie.test', 'protocol': 'nzb'}])
    movies._movie_mode_unsupported.clear()
    calls = []

    def request_xml(p, params, timeout):
        calls.append(params['t'])
        if params['t'] == 'movie':
            raise indexer_client.IndexerError('unsupported', code=203)
        return feed(('Dune.Part.Two.2024.1080p.WEB-DL', 'bad', 6 * GB, 0))
    monkeypatch.setattr(indexer_client, 'request_xml', request_xml)
    with engine.cx() as c:
        c.execute("INSERT INTO movie_blocklist(guid,movie_id,title,reason) VALUES('bad',?,?,?)", (mid, 'x', 'Stalled'))
        c.commit()
    out = movies.search_movie(mid, auto_grab=True)
    assert calls == ['movie', 'search']
    assert out['results'][0]['rejected_reason'] == 'Previously failed or stalled' and out['grabbed'] is None
    movies.search_movie(mid)
    assert calls[-1] == 'search' and calls.count('movie') == 1  # unsupported ID search is remembered


def test_upgrade_search_only_accepts_better_resolution(db, monkeypatch):
    mid = add(status='Downloaded')
    with engine.cx() as c:
        c.execute('UPDATE movies SET resolution=720 WHERE id=?', (mid,))
        c.commit()
    monkeypatch.setattr(movies, 'providers', lambda: [{'name': 'Geek', 'url': 'https://idx.test', 'protocol': 'nzb'}])
    monkeypatch.setattr(indexer_client, 'request_xml', lambda p, params, t: feed(('Dune.Part.Two.2024.720p.BluRay', 'a', 5 * GB, 0),
                                                                                 ('Dune.Part.Two.2024.1080p.WEB-DL', 'b', 7 * GB, 0)))
    out = movies.search_movie(mid)
    assert [r['guid'] for r in out['results'] if not r['rejected_reason']] == ['b']


def test_torrent_handoff_uses_movie_label(db, monkeypatch):
    import native_downloaders
    seen = {}

    def run(method, get, action, result=None):
        seen.update(method=method, label=get('TORRENT', 'torrent_label', ''), action=action)
        return 'abc123'
    monkeypatch.setattr(native_downloaders, 'run', run)
    engine.set_setting('TORRENT', 'torrent_label', 'tv')
    assert movies.handoff({'protocol': 'torrent', 'url': 'magnet:?x', 'title': 't'}) == ('uTorrent', 'abc123')
    assert seen == {'method': 'utorrent', 'label': 'movies', 'action': 'send'}


# ---------------------------------------------------------------- polling + import

def queued(mid, client='SABnzbd', protocol='nzb', release='Dune.Part.Two.2024.1080p.BluRay.x264-GRP', external='nzo1', hours_ago=1):
    stamp = (datetime.now() - timedelta(hours=hours_ago)).replace(microsecond=0).isoformat()
    with engine.cx() as c:
        cur = c.execute("""INSERT INTO movie_downloads(movie_id,client,protocol,release_name,guid,external_id,status,created_at,updated_at)
                           VALUES(?,?,?,?,?,?,'Queued',?,?)""", (mid, client, protocol, release, 'guid-' + external, external, stamp, stamp))
        c.execute("UPDATE movies SET status='Snatched' WHERE id=?", (mid,))
        c.commit()
        return cur.lastrowid


def test_completed_usenet_download_is_imported_with_plex_naming(db, monkeypatch):
    mid = add(title='Dune: Part Two')
    did = queued(mid)
    release_dir = db.downloads / 'movies' / 'Dune.Part.Two.2024.1080p.BluRay.x264-GRP'
    release_dir.mkdir(parents=True)
    (release_dir / 'dune.part.two.2024.1080p.bluray.x264-grp.mkv').write_bytes(b'x' * 2000)
    (release_dir / 'dune.part.two.2024.1080p.bluray.x264-grp.en.srt').write_text('1')
    (release_dir / 'sample.mkv').write_bytes(b'x' * 10)
    monkeypatch.setattr(movies, 'snapshot', lambda client: {'nzo1': {'status': 'Downloaded', 'progress': 1, 'path': ''}})
    refreshed = []
    monkeypatch.setattr(movies, 'refresh_media_servers', lambda path: refreshed.append(path))
    out = movies.run_downloads()
    assert out['import']['imported'] == 1, out
    folder = db.library / movies.movie_folder_name({'title': 'Dune: Part Two', 'year': 2024})
    target = folder / (folder.name + '.mkv')
    assert target.exists() and (folder / (folder.name + '.en.srt')).exists()
    assert not release_dir.exists()  # usenet leftovers are removed
    movie = movies.get_movie(mid)
    assert movie['status'] == 'Downloaded' and movie['resolution'] == 1080 and movie['file_path'] == str(target)
    with engine.cx() as c:
        assert c.execute('SELECT status FROM movie_downloads WHERE id=?', (did,)).fetchone()[0] == 'Completed'
    assert refreshed == [str(folder)]


def test_torrent_import_hardlinks_and_keeps_seeding_copy(db, monkeypatch):
    mid = add()
    queued(mid, client='uTorrent', protocol='torrent', external='HASH1')
    source = db.downloads / 'Dune.Part.Two.2024.1080p.WEB-DL.mkv'
    source.write_bytes(b'y' * 1000)
    monkeypatch.setattr(movies, 'snapshot', lambda client: {'hash1': {'status': 'Downloaded', 'progress': 1, 'path': str(source)}})
    monkeypatch.setattr(movies, 'refresh_media_servers', lambda path: None)
    movies.run_downloads()
    target = db.library / 'Dune Part Two (2024)' / 'Dune Part Two (2024).mkv'
    assert target.exists() and source.exists()
    if hasattr(os, 'link'):
        assert os.stat(source).st_ino == os.stat(target).st_ino


def test_upgrade_moves_old_file_to_share_trash(db, monkeypatch):
    import trash
    monkeypatch.setattr(trash, 'DB', db.path)
    mid = add()
    old_folder = db.library / 'Dune Part Two (2024)'
    old_folder.mkdir()
    old = old_folder / 'Dune Part Two (2024).avi'
    old.write_bytes(b'old')
    with engine.cx() as c:
        c.execute("UPDATE movies SET status='Downloaded',resolution=720,file_path=? WHERE id=?", (str(old), mid))
        c.commit()
    queued(mid, release='Dune.Part.Two.2024.1080p.BluRay.x264-GRP')
    with engine.cx() as c:
        c.execute("UPDATE movies SET status='Downloaded'")
        c.commit()
    folder = db.downloads / 'Dune.Part.Two.2024.1080p.BluRay.x264-GRP'
    folder.mkdir()
    (folder / 'movie.mkv').write_bytes(b'new' * 100)
    monkeypatch.setattr(movies, 'snapshot', lambda client: {'nzo1': {'status': 'Downloaded', 'progress': 1}})
    monkeypatch.setattr(movies, 'refresh_media_servers', lambda path: None)
    movies.run_downloads()
    assert not old.exists() and (old_folder / 'Dune Part Two (2024).mkv').exists()
    trashed = list((db.library / '.tvmanager-trash' / 'upgrades').rglob('*.avi'))
    assert len(trashed) == 1
    with engine.cx() as c:
        assert c.execute("SELECT category FROM trash_items").fetchone()[0] == 'upgrades'
    assert movies.get_movie(mid)['resolution'] == 1080
    engine.set_setting('Movies', 'library_scanned_at', '')
    monkeypatch.setattr(movies, '_plex_movies', lambda: ([], []))
    assert movies.scan_library()['folders'] == 1  # the trash folder is not read as a movie


def test_failed_and_stalled_downloads_are_blocklisted_and_retried(db, monkeypatch):
    failed = add(title='Failed Movie', tmdb_id=1, imdb_id='tt1')
    stalled = add(title='Stalled Movie', tmdb_id=2, imdb_id='tt2')
    unreachable = add(title='Client Down', tmdb_id=3, imdb_id='tt3')
    queued(failed, external='f1')
    queued(stalled, external='s1', hours_ago=40)
    queued(unreachable, client='uTorrent', protocol='torrent', external='u1', hours_ago=40)

    def snapshot(client):
        if client == 'uTorrent':
            raise ConnectionError('offline')
        return {'f1': {'status': 'Failed', 'error': 'Out of retention'}, 's1': {'status': 'Downloading', 'progress': 0.12}}
    monkeypatch.setattr(movies, 'snapshot', snapshot)
    out = movies.poll_downloads()
    assert out['changed'] == 2 and out['errors'] and 'offline' in out['errors'][0]
    with engine.cx() as c:
        rows = {r['movie_id']: dict(r) for r in c.execute('SELECT * FROM movie_downloads')}
        blocked = {r[0] for r in c.execute('SELECT guid FROM movie_blocklist')}
    assert rows[failed]['status'] == 'Failed' and 'Out of retention' in rows[failed]['message']
    assert rows[stalled]['status'] == 'Failed' and '12% done' in rows[stalled]['message']
    assert rows[unreachable]['status'] == 'Queued'  # an unreachable client is not treated as a stall
    assert blocked == {'guid-f1', 'guid-s1'}
    assert movies.get_movie(failed)['status'] == 'Wanted' and movies.get_movie(failed)['last_search'] is None


def test_simulation_mode_previews_import_without_moving(db, monkeypatch):
    mid = add()
    queued(mid)
    with engine.cx() as c:
        c.execute("UPDATE movie_downloads SET status='Downloaded'")
        c.commit()
    folder = db.downloads / 'Dune.Part.Two.2024.1080p.BluRay.x264-GRP'
    folder.mkdir()
    (folder / 'movie.mkv').write_bytes(b'z')
    engine.set_setting('TVManager', 'simulation_mode', '1')
    out = movies.import_completed()
    assert out['dry_run'] and out['items'][0]['dry_run'] and (folder / 'movie.mkv').exists()
    assert movies.get_movie(mid)['status'] == 'Snatched'


# ---------------------------------------------------------------- library + discovery

def test_library_scan_marks_owned_movies_and_discovery_skips_them(db, monkeypatch):
    owned = db.library / 'Oppenheimer (2023)'
    owned.mkdir()
    (owned / 'Oppenheimer (2023).mkv').write_bytes(b'o' * 50)
    (db.library / 'Empty Folder (2020)').mkdir()
    wanted = add(title='Oppenheimer', year=2023, tmdb_id=872585, imdb_id='tt15398776')
    monkeypatch.setattr(movies, '_plex_movies', lambda: ([{'title': 'Barbie', 'year': 2023, 'tmdb_id': 346698, 'imdb_id': None,
                                                           'file': 'D:/Movies/Barbie (2023)/Barbie.mkv', 'size': 5}], []))
    out = movies.scan_library()
    assert out['plex'] == 1 and out['folders'] == 1 and out['added'] == 1 and out['updated'] == 1
    assert movies.get_movie(wanted)['status'] == 'Downloaded'
    pages = {'/genre/movie/list': {'genres': [{'id': 99, 'name': 'Documentary'}, {'id': 10770, 'name': 'TV Movie'}]},
             '/discover/movie': {'total_pages': 1, 'results': [
                 {'id': 346698, 'title': 'Barbie', 'release_date': '2023-07-21'},
                 {'id': 872585, 'title': 'Oppenheimer', 'release_date': '2023-07-21'},
                 {'id': 11, 'title': 'New One', 'release_date': '2026-08-01'},
                 {'id': 12, 'title': 'New Two', 'release_date': '2026-08-02'}]}}
    params_seen = {}

    def tmdb(path, params=None):
        if path == '/discover/movie':
            params_seen.update(params)
        if path.startswith('/movie/'):
            tid = int(path.split('/')[2])
            return {'id': tid, 'title': 'New One' if tid == 11 else 'New Two', 'release_date': '2026-08-01',
                    'external_ids': {'imdb_id': f'tt{tid}'}, 'genres': [{'name': 'Drama'}],
                    'release_dates': {'results': [{'iso_3166_1': 'US', 'release_dates': [{'type': 3, 'release_date': '2026-08-01'},
                                                                                           {'type': 4, 'release_date': '2026-10-01T00:00:00Z'}]}]}}
        return pages[path]
    monkeypatch.setattr(movies, 'tmdb', tmdb)
    movies._genres.clear()
    engine.set_setting('Movies', 'max_auto_add_per_run', '1')
    result = movies.discover_auto()
    assert result['added'] == 1 and result['titles'] == ['New One']
    assert params_seen['with_release_type'] == '4|5' and params_seen['without_genres'] == '99,10770'
    assert params_seen['with_original_language'] == 'en'
    with engine.cx() as c:
        row = dict(c.execute('SELECT * FROM movies WHERE tmdb_id=11').fetchone())
    assert row['status'] == 'Wanted' and row['added_via'] == 'auto' and row['available_date'] == '2026-10-01' and row['imdb_id'] == 'tt11'


def test_search_waits_for_digital_release_and_backs_off(db):
    released = add(title='Out Now', tmdb_id=1, available_date='2020-01-01')
    add(title='Not Yet', tmdb_id=2, available_date='2999-01-01')
    recent = add(title='Searched', tmdb_id=3, available_date='2020-01-01')
    with engine.cx() as c:
        c.execute('UPDATE movies SET last_search=? WHERE id=?', (datetime.now().replace(microsecond=0).isoformat(), recent))
        c.commit()
    assert [m['id'] for m in movies.eligible_for_search(10)] == [released]


def test_settings_validation(db, tmp_path):
    with pytest.raises(ValueError, match='Folder not found'):
        movies.save_settings({'library_root': str(tmp_path / 'missing')})
    with pytest.raises(ValueError, match='positive number'):
        movies.save_settings({'min_rating': 'abc'})
    with pytest.raises(ValueError):
        movies.save_settings({'torrent_import_method': 'teleport'})
    out = movies.save_settings({'auto_add': 'false', 'min_rating': '7', 'unknown': 'x'})
    assert out['auto_add'] == '0' and out['min_rating'] == '7' and 'unknown' not in out


def test_jobs_are_registered_enabled_and_respect_off_switch(db):
    with engine.cx() as c:
        jobs = {r['name']: r['enabled'] for r in c.execute("SELECT * FROM scheduler_jobs WHERE name LIKE 'movie_%'")}
    assert jobs == {'movie_library_scan': 1, 'movie_discovery': 1, 'movie_search': 1, 'movie_downloads': 1}
    engine.set_setting('Movies', 'enabled', '0')
    assert movies.run_job('movie_search') == {'skipped': 'Movies are turned off'}


# ---------------------------------------------------------------- whole app

SCENARIO = textwrap.dedent(r'''
    import json
    import app
    client = app.app.test_client()
    out = {}
    page = client.get("/movies")
    out["page"] = [page.status_code, "movieSettings" in page.get_data(as_text=True)]
    out["nav"] = 'href="/movies"' in client.get("/dashboard").get_data(as_text=True)
    out["summary"] = client.get("/api/movies/summary").get_json()
    out["list"] = client.get("/api/movies?status=").get_json()
    out["bad_folder"] = client.post("/api/movies/settings", json={"library_root": "Z:/definitely/missing"}).status_code
    out["bad_job"] = client.post("/api/movies/jobs/nope/run").status_code
    import engine
    out["jobs"] = sorted(j["name"] for j in engine.jobs_public() if j["name"].startswith("movie_"))
    print(json.dumps(out))
''')


def test_movies_page_and_api_in_running_app():
    with tempfile.TemporaryDirectory() as tmp:
        code = Path(tmp) / 'app'
        shutil.copytree(ROOT, code, ignore=shutil.ignore_patterns(
            '.git', 'tests', '*.db*', 'managed_trash', 'logs', '.runtime', '__pycache__', 'imports', 'backups'))
        (code / 'scenario.py').write_text(SCENARIO, encoding='utf-8')
        r = subprocess.run([sys.executable, 'scenario.py'], cwd=code, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, r.stderr[-3000:]
        out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out['page'] == [200, True] and out['nav']
    assert out['summary']['settings']['enabled'] == '1' and len(out['summary']['jobs']) == 4
    assert out['list']['movies'] == [] and out['list']['total'] == 0
    assert out['bad_folder'] == 400 and out['bad_job'] == 404
    assert out['jobs'] == ['movie_discovery', 'movie_downloads', 'movie_library_scan', 'movie_search']
