"""v18.34.0: Movies > Discover can hide movies that are already downloaded."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import movies  # noqa: E402
from test_v18_26_0_movies import db  # noqa: E402,F401


def tmdb_pages(monkeypatch, pages):
    calls = []

    def tmdb(path, params=None):
        page = int((params or {}).get('page', 1))
        calls.append(page)
        return {'results': pages.get(page, []), 'total_pages': len(pages)}
    monkeypatch.setattr(movies, 'tmdb', tmdb)
    return calls


def item(i, title, year=2025):
    return {'id': i, 'title': title, 'release_date': f'{year}-05-01', 'vote_average': 7, 'vote_count': 500}


def owned(db, tmdb_id, title, year=2025):
    with movies.cx() as c:
        c.execute("INSERT INTO movies(tmdb_id,title,year,status,added_at) VALUES(?,?,?,'Downloaded',datetime('now'))", (tmdb_id, title, year))


def test_default_shows_downloaded_with_status(db, monkeypatch):
    tmdb_pages(monkeypatch, {1: [item(1, 'Alpha'), item(2, 'Beta')]})
    owned(db, 1, 'Alpha')
    d = movies.discover_list('trending')
    assert [(m['title'], m['status']) for m in d['results']] == [('Alpha', 'Downloaded'), ('Beta', None)]
    assert d['hidden'] == 0 and d['page'] == 1


def test_hide_downloaded_drops_owned_and_library_matches_and_fills_the_page(db, monkeypatch):
    pages = {1: [item(1, 'Alpha'), item(2, 'Beta')] + [item(100 + n, f'Old {n}') for n in range(18)],
             2: [item(200 + n, f'New {n}') for n in range(20)], 3: [item(300, 'Later')]}
    for n in range(18):
        owned(db, None, f'Old {n}')  # found in the library: matched by title and year
    owned(db, 1, 'Alpha')
    calls = tmdb_pages(monkeypatch, pages)
    d = movies.discover_list('trending', hide_downloaded=True)
    titles = [m['title'] for m in d['results']]
    assert 'Alpha' not in titles and not any(t.startswith('Old') for t in titles)
    assert titles[0] == 'Beta' and len(titles) == 21  # page 1 left one, so page 2 was read too
    assert d['hidden'] == 19 and d['page'] == 2 and calls == [1, 2]
    d2 = movies.discover_list('trending', page=d['page'] + 1, hide_downloaded=True)
    assert [m['title'] for m in d2['results']] == ['Later'] and d2['page'] == 3


def test_wanted_movies_are_not_hidden(db, monkeypatch):
    tmdb_pages(monkeypatch, {1: [item(1, 'Alpha')]})
    with movies.cx() as c:
        c.execute("INSERT INTO movies(tmdb_id,title,year,status,added_at) VALUES(1,'Alpha',2025,'Wanted',datetime('now'))")
    assert [m['status'] for m in movies.discover_list('trending', hide_downloaded=True)['results']] == ['Wanted']


def test_page_has_checkbox_and_route_passes_it():
    html = (ROOT / 'templates' / 'movies.html').read_text(encoding='utf-8')
    js = (ROOT / 'static' / 'movies.js').read_text(encoding='utf-8')
    routes = (ROOT / 'movies_routes.py').read_text(encoding='utf-8')
    assert 'id="discoverHideDownloaded"' in html and 'Hide movies already downloaded' in html
    assert "q.set('hide_downloaded','1')" in js and 'tvmanager.movies.discover.hideDownloaded' in js
    assert "hide_downloaded=a.get('hide_downloaded')" in routes
