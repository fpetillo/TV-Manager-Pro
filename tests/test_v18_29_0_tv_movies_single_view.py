"""v18.29.0: TV shows and movies in one view — dashboard, search, schedule, queue, launchpad and movie detail."""
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine  # noqa: E402
import movies  # noqa: E402
from test_v18_26_0_movies import db  # noqa: E402,F401  (shared fixture)


def seed_movies():
    soon = (date.today() + timedelta(days=5)).isoformat()
    now = datetime.now().replace(microsecond=0)
    with engine.cx() as c:
        rows = [(1, 'Dune: Part Two', 2024, 'Downloaded', 'auto', '2024-05-01', (now - timedelta(hours=3)).isoformat()),
                (2, 'Barbie', 2023, 'Downloaded', 'plex', '2023-09-01', None),
                (3, 'Inside Out 2', 2024, 'Wanted', 'auto', '2024-08-01', None),
                (4, 'The Wild Robot', 2024, 'Wanted', 'manual', soon, None),
                (5, 'Deadpool & Wolverine', 2024, 'Snatched', 'auto', '2024-10-01', None)]
        for tid, title, year, status, via, avail, dl in rows:
            c.execute("INSERT INTO movies(tmdb_id,imdb_id,title,year,status,monitored,added_via,available_date,downloaded_at) VALUES(?,?,?,?,?,1,?,?,?)",
                      (tid, f'tt{tid}', title, year, status, via, avail, dl))
        stamp = now.isoformat()
        for movie_id, client, release, status in [(5, 'SABnzbd', 'Deadpool.and.Wolverine.2024.1080p.WEB-DL', 'Downloading'),
                                                  (1, 'SABnzbd', 'Dune.Part.Two.2024.1080p.BluRay', 'Completed'),
                                                  (3, 'uTorrent', 'Inside.Out.2.2024.1080p.WEB', 'Failed')]:
            c.execute("INSERT INTO movie_downloads(movie_id,client,protocol,release_name,status,progress,created_at,updated_at) VALUES(?,?,'nzb',?,?,0.4,?,?)",
                      (movie_id, client, release, status, stamp, stamp))
        c.commit()
    return soon


def ready_settings(**over):
    base = {'enabled': '1', 'effective_library_root': 'M:/Movies', 'tmdb_configured': True, 'indexers': 2,
            'automation_enabled': True, 'simulation_mode': False}
    return lambda: dict(base, **over)


def test_dashboard_summary_counts_wanted_and_coming_movies(db, monkeypatch):
    soon = seed_movies()
    monkeypatch.setattr(movies, 'settings_public', ready_settings())
    d = movies.dashboard_summary()
    c = d['counts']
    assert (c['owned'], c['wanted'], c['waiting'], c['downloading'], c['imported_week'], c['failed_week']) == (2, 1, 1, 1, 1, 1)
    assert [m['title'] for m in d['recent']] == ['Dune: Part Two']  # movies found in Plex are not "recently added"
    assert d['next_release']['title'] == 'The Wild Robot' and d['next_release']['available_date'] == soon
    assert d['active'][0]['title'] == 'Deadpool & Wolverine' and d['running'] is True and d['problems'] == []


def test_setup_problems_reach_dashboard_and_insights(db, monkeypatch):
    seed_movies()
    monkeypatch.setattr(movies, 'settings_public', ready_settings(effective_library_root='', tmdb_configured=False, indexers=0))
    d = movies.dashboard_summary()
    assert [p['title'] for p in d['problems']] == ['No movie destination folder yet', 'TMDb is not configured',
                                                   'No indexers with a matching download client']
    assert d['running'] is False
    titles = [i['title'] for i in movies.insights()]
    assert titles[:2] == ['Movies: No movie destination folder yet', 'Movies: TMDb is not configured']
    assert {'1 movie download failed this week', '1 movie wanted', '1 movie added to Plex this week'} <= set(titles)


def test_calendar_search_and_detail(db):
    seed_movies()
    end = (date.today() + timedelta(days=14)).isoformat()
    assert [m['title'] for m in movies.calendar(date.today().isoformat(), end)] == ['The Wild Robot']
    assert movies.command_search('dune') == [{'type': 'movie', 'id': 1, 'title': 'Dune: Part Two (2024)',
                                              'subtitle': 'Movie in library', 'href': '/movie/1'}]
    assert movies.command_search('tt3')[0]['title'] == 'Inside Out 2 (2024)'
    with engine.cx() as c:
        c.execute("CREATE TABLE IF NOT EXISTS activity_log(id INTEGER PRIMARY KEY, level TEXT, event_type TEXT, show_id INT, episode_id INT, message TEXT, data TEXT, created_at TEXT)")
        c.execute("""INSERT INTO activity_log(level,event_type,message,data,created_at) VALUES('info','movie_imported','Imported Dune','{"movie_id": 1, "replaced": null}','2026-11-22 10:00:00')""")
        c.execute("""INSERT INTO activity_log(level,event_type,message,data,created_at) VALUES('info','movie_imported','Imported other','{"movie_id": 11}','2026-11-22 10:00:00')""")
        c.commit()
    detail = movies.detail(1)
    assert detail['movie']['title'] == 'Dune: Part Two' and detail['movie']['available'] is True
    assert [d['status'] for d in detail['downloads']] == ['Completed']
    assert [e['message'] for e in detail['events']] == ['Imported Dune']


def test_movie_notifications_name_the_movie(monkeypatch):
    import notifiers
    sent = {}

    class Response:
        ok = True
        status_code = 200
        text = ''

    def post(url, json=None, data=None, headers=None, timeout=None, **kw):
        sent.update(json or data or {})
        return Response()
    monkeypatch.setattr(notifiers.requests, 'post', post)
    notifiers.send({'kind': 'discord', 'url': 'https://discord.test/hook'}, 'snatched',
                   {'movie': 'Dune', 'release': 'Dune.2024.1080p', 'message': 'Movie snatched: Dune (2024) — Dune.2024.1080p'})
    assert 'Movie snatched: Dune (2024)' in sent['content']


def test_templates_and_navigation_present_tv_and_movies_together():
    def t(name):
        return (ROOT / 'templates' / name).read_text(encoding='utf-8')
    dashboard = t('dashboard.html')
    assert 'media-tv' in dashboard and 'media-movies' in dashboard and 'recentRail' in dashboard and 'data-filter="movie"' in dashboard
    nav = t('_nav.html')
    assert nav.index('href="/manager"') < nav.index('href="/movies"') < nav.index('href="/manage"')
    assert 'TV shows & movies' in nav
    assert 'upcomingMoviesPanel' in t('upcoming.html') and 'movieQueuePanel' in t('queue.html')
    assert 'queue_movies.js' in t('queue.html') and 'movie_detail.js' in t('movie_detail.html')
    assert 'Operate your TV and movie library' in t('launchpad.html')
    for name in ['dashboard.html', 'movies.html', 'movie_detail.html', 'upcoming.html']:
        assert 'Search shows, episodes, movies, pages, IDs' in t(name), name


SCENARIO = textwrap.dedent(r'''
    import json
    from datetime import date, timedelta
    import app, engine
    soon = (date.today() + timedelta(days=4)).isoformat()
    with engine.cx() as c:
        c.execute("INSERT INTO movies(tmdb_id,imdb_id,title,year,status,monitored,added_via,available_date,downloaded_at) VALUES(1,'tt1','Dune: Part Two',2024,'Downloaded',1,'auto','2024-05-01','2026-11-22T10:00:00')")
        c.execute("INSERT INTO movies(tmdb_id,title,year,status,monitored,added_via,available_date) VALUES(2,'The Wild Robot',2024,'Wanted',1,'manual',?)", (soon,))
        c.execute("INSERT INTO movie_downloads(movie_id,client,protocol,release_name,status,created_at,updated_at) VALUES(1,'SABnzbd','nzb','Dune.Part.Two.2024.1080p.BluRay','Completed','2026-11-22T09:00:00','2026-11-22T10:00:00')")
        c.commit()
    client = app.app.test_client()
    full = client.get("/api/dashboard/full").get_json()
    search = client.get("/api/command/search?q=wild").get_json()["results"]
    nav_search = client.get("/api/command/search?q=movi").get_json()["results"]
    insights = client.get("/api/insights").get_json()["results"]
    launch = client.get("/api/launchpad/summary").get_json()
    cal = client.get("/api/movies/calendar?days=14").get_json()["results"]
    ics = client.get("/calendar.ics").get_data(as_text=True)
    detail = client.get("/api/movies/1/detail").get_json()
    pages = {p: client.get(p).status_code for p in ["/dashboard", "/movie/1", "/upcoming", "/queue", "/launchpad", "/movies"]}
    print(json.dumps({"full_movies": full["movies"]["counts"], "movie_downloads": [d["title"] for d in full["movie_downloads"]],
                      "search": search, "nav_search": [r["href"] for r in nav_search], "insights": [i["title"] for i in insights],
                      "launch_movies": launch.get("movies"), "cal": [m["title"] for m in cal],
                      "ics": "SUMMARY:Movie: The Wild Robot (2024)" in ics.replace("\r\n ", ""),
                      "detail": detail["movie"]["title"], "pages": pages}))
''')


def test_tv_and_movies_together_in_running_app():
    with tempfile.TemporaryDirectory() as tmp:
        code = Path(tmp) / 'app'
        shutil.copytree(ROOT, code, ignore=shutil.ignore_patterns(
            '.git', 'tests', '*.db*', 'managed_trash', 'logs', '.runtime', '__pycache__', 'imports', 'backups'))
        (code / 'scenario.py').write_text(SCENARIO, encoding='utf-8')
        r = subprocess.run([sys.executable, 'scenario.py'], cwd=code, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, r.stderr[-3000:]
        out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out['full_movies']['owned'] == 1 and out['full_movies']['waiting'] == 1
    assert out['movie_downloads'] == ['Dune: Part Two']
    assert out['search'][0] == {'type': 'movie', 'id': 2, 'title': 'The Wild Robot (2024)', 'subtitle': 'Wanted movie', 'href': '/movie/2'}
    assert '/movies' in out['nav_search']
    assert any(t.startswith('Movies: ') for t in out['insights'])
    assert out['launch_movies']['owned'] == 1
    assert out['cal'] == ['The Wild Robot'] and out['ics'] and out['detail'] == 'Dune: Part Two'
    assert set(out['pages'].values()) == {200}
