"""v18.31.0/v18.32.0: movie destination folders set on this server; every Plex server scans its movie libraries."""
import json
import sys
from collections import namedtuple
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import advanced  # noqa: E402
import engine  # noqa: E402
import movies  # noqa: E402
from test_v18_26_0_movies import db, queued, add  # noqa: E402,F401

Usage = namedtuple('Usage', 'total used free')
GB = 1024 ** 3


def drives(monkeypatch, free_by_path):
    def usage(path):
        for prefix, free in free_by_path.items():
            if str(path).startswith(str(prefix)):
                return Usage(4000 * GB, 0, free * GB)
        raise OSError('no drive')
    monkeypatch.setattr(movies.shutil, 'disk_usage', usage)


def test_destination_folders_are_configured_here_and_validated(db, tmp_path):
    a, b = tmp_path / 'Media_5' / 'Movies', tmp_path / 'Media_6' / 'Movies'
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    s = movies.save_settings({'destination_folders': f'{a}\n{b}'})
    assert s['destination_list'] == [str(a), str(b)] and s['effective_library_root'] == str(a)
    assert engine.get_setting('Movies', 'library_root') == str(a)  # older single-folder setting kept in step
    with pytest.raises(ValueError, match='not found from this server'):
        movies.save_settings({'destination_folders': str(tmp_path / 'missing')})
    # Older installs with only library_root keep working.
    engine.set_setting('Movies', 'destination_folders', '')
    assert movies.destination_folders() == [str(a)]


def test_destination_choice_most_free_in_order_and_upgrades_stay_put(db, tmp_path, monkeypatch):
    a, b = tmp_path / 'A', tmp_path / 'B'
    a.mkdir()
    b.mkdir()
    engine.set_setting('Movies', 'destination_folders', f'{a}\n{b}')
    drives(monkeypatch, {a: 120, b: 900})
    assert movies.destination_for({}, 10 * GB)[0] == str(b)  # most free space
    engine.set_setting('Movies', 'destination_rule', 'in_order')
    assert movies.destination_for({}, 10 * GB)[0] == str(a)  # first folder that keeps the 50 GB reserve
    drives(monkeypatch, {a: 30, b: 900})
    assert movies.destination_for({}, 10 * GB)[0] == str(b)  # A would drop below the reserve
    old = {'file_path': str(a / 'Dune (2024)' / 'Dune (2024).mkv')}
    assert movies.destination_for(old, 10 * GB) == (str(a), 'same folder as the current copy')
    drives(monkeypatch, {a: 20, b: 25})
    assert movies.destination_for({}, 10 * GB)[0] == str(b)  # all below reserve: roomiest that fits
    assert movies.destination_for({}, 40 * GB)[0] is None


class FakeResponse:
    def __init__(self, content=b''):
        self.content = content

    def raise_for_status(self):
        pass


SECTIONS = b'''<MediaContainer>
<Directory key="1" type="show" title="TV"><Location path="/data/tv"/></Directory>
<Directory key="2" type="movie" title="Movies"><Location path="/data/media5/movies"/></Directory>
<Directory key="3" type="movie" title="Movies 4K"><Location path="/data/4k"/></Directory>
</MediaContainer>'''


def plex(monkeypatch):
    calls = []

    def get(url, headers=None, params=None, timeout=None):
        calls.append((url, dict(params or {})))
        return FakeResponse(SECTIONS if url.endswith('/library/sections') else b'')
    monkeypatch.setattr(advanced.requests, 'get', get)
    monkeypatch.setattr(advanced, 'media_servers', lambda: [{'id': 1, 'name': 'Den', 'kind': 'plex', 'enabled': 1},
                                                             {'id': 2, 'name': 'Office', 'kind': 'plex', 'enabled': 1}])
    monkeypatch.setattr(advanced, 'media_server', lambda sid, masked=True: {'id': sid, 'url': f'http://plex{sid}:32400', 'token': 't'})
    return calls


def test_every_plex_server_scans_all_its_movie_libraries_without_configuration(db, monkeypatch):
    # v18.32.0: no folder translation; each Plex server already knows its libraries.
    calls = plex(monkeypatch)
    out = movies.refresh_media_servers(r'\\nas\Media_5\Movies\Dune (2024)')
    refreshes = [c for c in calls if c[0].endswith('/refresh')]
    for host in ('plex1', 'plex2'):
        assert (f'http://{host}:32400/library/sections/2/refresh', {}) in refreshes
        assert (f'http://{host}:32400/library/sections/3/refresh', {}) in refreshes
    assert not any('/sections/1/' in c[0] for c in refreshes)  # never the TV library
    assert movies._scan_note(out) == 'Media servers — Den: scanning 2 movie libraries; Office: scanning 2 movie libraries.'
    assert 'plex_path_map' not in movies.settings_public()


def test_import_uses_destination_with_room_and_reports_settings(db, monkeypatch, tmp_path):
    a, b = tmp_path / 'A', tmp_path / 'B'
    a.mkdir()
    b.mkdir()
    engine.set_setting('Movies', 'destination_folders', f'{a}\n{b}')
    drives(monkeypatch, {a: 10, b: 800})
    mid = add()
    queued(mid)
    folder = db.downloads / 'Dune.Part.Two.2024.1080p.BluRay.x264-GRP'
    folder.mkdir()
    (folder / 'movie.mkv').write_bytes(b'z' * 300)
    monkeypatch.setattr(movies, 'snapshot', lambda client: {'nzo1': {'status': 'Downloaded', 'progress': 1}})
    scanned = []
    monkeypatch.setattr(movies, 'refresh_media_servers', lambda path: scanned.append(path) or [])
    movies.run_downloads()
    assert movies.get_movie(mid)['file_path'].startswith(str(b))
    assert scanned == [str(b / 'Dune Part Two (2024)')]
    s = movies.settings_public()
    assert [d['path'] for d in s['destination_status']] == [str(a), str(b)] and s['destination_status'][1]['free_gb'] == 800.0
    assert 'plex_servers' in s
