"""v18.30.0: imported movies land where Plex looks, Plex scan results are recorded, and misplaced movies can be moved."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine  # noqa: E402
import movies  # noqa: E402
from test_v18_26_0_movies import db, queued, add  # noqa: E402,F401  (shared fixture and helpers)


def scan_report(locations, complete=True):
    engine.set_setting('Movies', 'last_scan_report', json.dumps({
        'complete': complete, 'sources': [{'kind': 'plex', 'server': 'Plex', 'library': 'Movies', 'locations': locations, 'ok': True}]}))


def test_utorrent_single_file_save_folder_gets_the_torrent_name(db, monkeypatch, tmp_path):
    import native_downloaders

    class Fake:
        def __init__(self, get):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def connect(self):
            pass

        def rpc(self, params):
            def row(h, name, path):
                return [h, 1, name, 0, 1000] + [0] * 21 + [path]
            return {'torrents': [row('AA', 'Movie.2024.1080p.mkv', str(tmp_path / 'complete')),
                                 row('BB', 'Other.2024.1080p', str(tmp_path / 'complete' / 'Other.2024.1080p'))]}
    monkeypatch.setattr(native_downloaders, 'UTorrent', Fake)
    snap = movies._utorrent_snapshot()
    assert snap['aa']['path'] == os.path.join(str(tmp_path / 'complete'), 'Movie.2024.1080p.mkv')
    assert snap['bb']['path'] == str(tmp_path / 'complete' / 'Other.2024.1080p')


def test_a_whole_download_folder_is_never_imported_as_one_movie(db):
    (db.downloads / 'Some.Other.Movie.2023.1080p.mkv').write_bytes(b'x' * 5000)
    mid = add()
    did = queued(mid, client='uTorrent', protocol='torrent', release='Dune.Part.Two.2024.1080p.WEB-DL', external='h1')
    with engine.cx() as c:
        c.execute("UPDATE movie_downloads SET status='Downloaded',content_path=? WHERE id=?", (str(db.downloads), did))
        c.commit()
        row = dict(c.execute('SELECT * FROM movie_downloads WHERE id=?', (did,)).fetchone())
    assert movies.locate(row) is None  # the download root itself is not the movie
    (db.downloads / 'Dune.Part.Two.2024.1080p.WEB-DL.mkv').write_bytes(b'y' * 100)
    assert movies.locate(row).name == 'Dune.Part.Two.2024.1080p.WEB-DL.mkv'


def test_library_folder_status_against_plex_libraries(db, tmp_path):
    plex_movies = tmp_path / 'Media_3' / 'Movies'
    plex_movies.mkdir(parents=True)
    scan_report([str(plex_movies)])
    assert movies.library_plex_status(str(plex_movies / 'New')) == 'ok'
    assert movies.library_plex_status(str(db.library)) == 'outside'
    s = movies.settings_public()
    assert s['library_plex_status'] == 'outside' and s['plex_movie_folders'][0]['reachable'] is True
    assert ('The movie library folder is not in a Plex movie library', '/movies#settings') in movies._setup_problems(s)
    engine.set_setting('Movies', 'last_scan_report', json.dumps({'complete': True, 'sources': []}))
    assert movies.library_plex_status(str(db.library)) == 'no_plex'


def test_detection_does_not_guess_a_folder_plex_never_scans(db, monkeypatch, tmp_path):
    tv = tmp_path / 'Media_5' / 'TV'
    tv.mkdir(parents=True)
    (tmp_path / 'Media_5' / 'Movies').mkdir()
    import library_destinations
    monkeypatch.setattr(library_destinations, 'library_roots', lambda value: [str(tv)])
    assert movies.detect_library_root(['/volume1/Movies']) == ''  # Plex has a movie library, but not reachable here
    assert movies.detect_library_root([]) == str(tmp_path / 'Media_5' / 'Movies')  # no Plex at all: sibling is fine


def test_import_records_destination_and_plex_scan(db, monkeypatch):
    scan_report([str(db.library)])
    mid = add()
    did = queued(mid)
    folder = db.downloads / 'Dune.Part.Two.2024.1080p.BluRay.x264-GRP'
    folder.mkdir()
    (folder / 'movie.mkv').write_bytes(b'z' * 300)
    monkeypatch.setattr(movies, 'snapshot', lambda client: {'nzo1': {'status': 'Downloaded', 'progress': 1}})
    monkeypatch.setattr(movies, 'refresh_media_servers', lambda path: [{'server': 'Plex Den', 'ok': True, 'targeted': True}])
    movies.run_downloads()
    with engine.cx() as c:
        message = c.execute('SELECT message FROM movie_downloads WHERE id=?', (did,)).fetchone()[0]
    assert message.startswith('Imported by move to ') and 'Dune Part Two (2024).mkv' in message
    imported = [a for a in db.logs if a[0] == 'movie_imported'][0]
    assert 'Plex — Plex Den: scanned the movie folder.' in imported[1] and imported[2] == 'info'


def test_import_outside_plex_is_logged_as_warning(db, monkeypatch, tmp_path):
    (tmp_path / 'PlexMovies').mkdir()
    scan_report([str(tmp_path / 'PlexMovies')])
    mid = add()
    queued(mid)
    folder = db.downloads / 'Dune.Part.Two.2024.1080p.BluRay.x264-GRP'
    folder.mkdir()
    (folder / 'movie.mkv').write_bytes(b'z' * 300)
    monkeypatch.setattr(movies, 'snapshot', lambda client: {'nzo1': {'status': 'Downloaded', 'progress': 1}})
    monkeypatch.setattr(movies, 'refresh_media_servers', lambda path: [])
    movies.run_downloads()
    imported = [a for a in db.logs if a[0] == 'movie_imported'][0]
    assert imported[2] == 'warning' and 'not in any Plex movie library' in imported[1]


def test_move_imported_movies_into_the_plex_folder(db, monkeypatch, tmp_path):
    wrong = db.library  # where earlier imports went
    plex_movies = tmp_path / 'PlexMovies'
    plex_movies.mkdir()
    a = add(title='The Drama', year=2026, tmdb_id=1, imdb_id='tt1', status='Downloaded')
    b = add(title='Hokum', year=2026, tmdb_id=2, imdb_id='tt2', status='Downloaded')
    c_ = add(title='Barbie', year=2023, tmdb_id=3, imdb_id='tt3', status='Downloaded')
    paths = {}
    for mid, title in [(a, 'The Drama (2026)'), (b, 'Hokum (2026)')]:
        (wrong / title).mkdir()
        (wrong / title / f'{title}.mkv').write_bytes(b'm')
        paths[mid] = wrong / title / f'{title}.mkv'
    (plex_movies / 'Hokum (2026)').mkdir()  # already there: skipped, never overwritten
    with engine.cx() as c:
        for mid, path in paths.items():
            c.execute("UPDATE movies SET file_path=?,added_via='auto' WHERE id=?", (str(path), mid))
        c.execute("UPDATE movies SET file_path='X:/Barbie.mkv',added_via='plex' WHERE id=?", (c_,))  # Plex-owned: untouched
        c.commit()
    engine.set_setting('Movies', 'library_root', str(plex_movies))
    scan_report([str(plex_movies)])
    plan = movies.relocation_plan()
    assert [i['title'] for i in plan['items']] == ['The Drama'] and plan['skipped'][0]['title'] == 'Hokum'
    refreshed = []
    monkeypatch.setattr(movies, 'refresh_media_servers', lambda path: refreshed.append(path) or [])
    out = movies.relocate_imported(background=False)
    assert out['started'] is True
    moved = plex_movies / 'The Drama (2026)' / 'The Drama (2026).mkv'
    assert moved.exists() and not paths[a].exists() and paths[b].exists()
    assert movies.get_movie(a)['file_path'] == str(moved) and refreshed == [str(plex_movies)]
    assert movies.relocation_plan()['items'] == []
