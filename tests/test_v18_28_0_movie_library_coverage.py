"""v18.28.0: the movie library scan covers every Plex server, every movie library and every movie folder."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine  # noqa: E402
import movies  # noqa: E402
from test_v18_26_0_movies import db  # noqa: E402,F401  (shared fixture)


class Response:
    def __init__(self, xml):
        self.content = xml.encode()


def video(title, year, guid):
    return f'<Video title="{title}" year="{year}"><Guid id="{guid}"/><Media><Part file="X:/{title}.mkv" size="1"/></Media></Video>'


def fake_plex(monkeypatch, servers, libraries, failing=()):
    """libraries: {(server, key): (title, [locations], [videos])}."""
    import advanced
    monkeypatch.setattr(advanced, 'media_servers', lambda: [{'id': i, 'name': n, 'kind': 'plex', 'enabled': 1} for i, n in enumerate(servers)])
    monkeypatch.setattr(advanced, 'media_server', lambda sid, masked=False: {'url': f'http://{servers[sid]}', 'token': 't'})
    calls = []

    def get(url, headers=None, params=None, timeout=None):
        host = url.split('//')[1].split('/')[0]
        calls.append((url, dict(params or {})))
        if host in failing:
            raise ConnectionError('server is off')
        if url.endswith('/library/sections'):
            dirs = ''.join(f'<Directory key="{key}" type="movie" title="{title}">' + ''.join(f'<Location path="{p}"/>' for p in locs) + '</Directory>'
                           for (srv, key), (title, locs, _v) in libraries.items() if srv == host)
            return Response(f'<MediaContainer><Directory key="9" type="show" title="TV"/>{dirs}</MediaContainer>')
        key = url.split('/sections/')[1].split('/')[0]
        items = libraries[(host, key)][2]
        start, size = int(params['X-Plex-Container-Start']), int(params['X-Plex-Container-Size'])
        return Response(f'<MediaContainer totalSize="{len(items)}">{"".join(items[start:start + size])}</MediaContainer>')
    monkeypatch.setattr(movies.requests, 'get', get)
    return calls


def test_every_plex_server_and_library_is_read_page_by_page(db, monkeypatch):
    monkeypatch.setattr(movies, 'PLEX_PAGE', 2)
    big = [video(f'Film {i}', 2000 + i, f'tmdb://{100 + i}') for i in range(5)]
    calls = fake_plex(monkeypatch, ['plex1', 'plex2'], {
        ('plex1', '1'): ('Movies', ['D:/Movies', 'E:/Movies'], big),
        ('plex1', '2'): ('Movies 4K', ['F:/4K'], [video('Dune', 2021, 'imdb://tt1160419')]),
        ('plex2', '7'): ('Kids', ['\\\\NAS\\Kids'], [video('Up', 2009, 'com.plexapp.agents.imdb://tt1049413?lang=en')]),
    })
    items, locations, sources = movies._plex_movies()
    assert len(items) == 7
    assert locations == ['D:/Movies', 'E:/Movies', 'F:/4K', '\\\\NAS\\Kids']
    assert [(s['server'], s['library'], s['count'], s['ok']) for s in sources] == [
        ('plex1', 'Movies', 5, True), ('plex1', 'Movies 4K', 1, True), ('plex2', 'Kids', 1, True)]
    pages = [p['X-Plex-Container-Start'] for u, p in calls if '/sections/1/' in u]
    assert pages == [0, 2, 4]
    assert {i['imdb_id'] for i in items if i['imdb_id']} == {'tt1160419', 'tt1049413'}


def test_unreachable_plex_server_is_reported_and_pauses_discovery(db, monkeypatch):
    fake_plex(monkeypatch, ['plex1', 'plex2'], {('plex1', '1'): ('Movies', [], [video('Heat', 1995, 'tmdb://949')])}, failing={'plex2'})
    out = movies.scan_library()
    assert out['complete'] is False and out['plex'] == 1
    report = json.loads(engine.get_setting('Movies', 'last_scan_report', '{}'))
    bad = [s for s in report['sources'] if not s['ok']]
    assert bad[0]['server'] == 'plex2' and 'Could not reach' in bad[0]['error']
    monkeypatch.setattr(movies, 'tmdb', lambda *a, **k: pytest.fail('discovery must not call TMDb'))
    skipped = movies.discover_auto()
    assert skipped['added'] == 0 and 'plex2' in skipped['skipped']


def test_all_movie_folders_are_scanned(db, monkeypatch, tmp_path):
    def movie(folder, name, ext='.mkv'):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (name + ext)).write_bytes(b'v' * 20)
    movie(db.library / 'Heat (1995)', 'Heat (1995)')                         # import folder
    e = tmp_path / 'E_Movies'
    movie(e / 'A' / 'Alien (1979)', 'Alien (1979)')                          # grouped by letter
    movie(e / 'Action' / 'Speed (1994)', 'speed.1994.1080p')                 # grouped by genre
    movie(e, 'Jaws (1975)')                                                  # loose file in the root
    movie(e / '.tvmanager-trash' / 'upgrades', 'Old (2001)')                 # trash is skipped
    nas = tmp_path / 'NAS_Kids'
    movie(nas / 'Up [2009] {tmdb-14160}', 'Up')
    nested = e / 'A'                                                         # inside another folder: read once
    engine.set_setting('Movies', 'extra_library_folders', str(e))
    monkeypatch.setattr(movies, '_plex_movies', lambda: ([], [str(nas), str(nested), str(tmp_path / 'Offline')], [
        {'kind': 'plex', 'server': 'plex1', 'library': 'Movies', 'locations': [str(nas)], 'count': 0, 'ok': True, 'error': ''}]))
    out = movies.scan_library()
    assert out['complete'] is True and out['folders'] == 5 and out['owned'] == 5
    folders = {s['path']: s for s in out['sources'] if s['kind'] == 'folder'}
    assert folders[str(db.library)]['count'] == 1
    assert folders[str(e)]['count'] == 3
    assert folders[str(nas)]['count'] == 1
    assert folders[str(nested)]['error'].startswith('Read with')
    assert folders[str(tmp_path / 'Offline')]['ok'] is True and 'Covered by the Plex' in folders[str(tmp_path / 'Offline')]['error']
    engine.set_setting('Movies', 'extra_library_folders', str(tmp_path / 'Gone'))
    gone = [s for s in movies.scan_library()['sources'] if s.get('path') == str(tmp_path / 'Gone')][0]
    assert gone['ok'] is False and 'Not reachable' in gone['error']
    with engine.cx() as c:
        owned = {(r['title'], r['year'], r['tmdb_id']) for r in c.execute("SELECT title,year,tmdb_id FROM movies WHERE status='Downloaded'")}
    assert owned == {('Heat', 1995, None), ('Alien', 1979, None), ('Speed', 1994, None), ('Jaws', 1975, None), ('Up', 2009, 14160)}


def test_movie_owned_by_imdb_id_is_not_added_again(db, monkeypatch):
    with engine.cx() as c:
        c.execute("INSERT INTO movies(imdb_id,title,year,status) VALUES('tt0113277','Heat',1995,'Downloaded')")
        c.commit()
    monkeypatch.setattr(movies, 'tmdb', lambda path, params=None: {'id': 949, 'title': 'Heat (Director\u2019s Cut)', 'release_date': '1995-12-15',
                                                                   'external_ids': {'imdb_id': 'tt0113277'}})
    result = movies.add_movie(949, added_via='auto')
    assert result['created'] is False and result['movie']['tmdb_id'] == 949 and result['movie']['status'] == 'Downloaded'


def test_other_movie_folders_setting_is_validated(db, tmp_path):
    good = tmp_path / 'Good'
    good.mkdir()
    with pytest.raises(ValueError, match='Folder not found'):
        movies.save_settings({'extra_library_folders': f'{good}\n{tmp_path / "Missing"}'})
    out = movies.save_settings({'extra_library_folders': f' "{good}" ;\n\n'})
    assert out['extra_library_folders'] == str(good)
