"""Movies: library index, TMDb discovery, indexer search, download handoff, polling and import.

The movie workflow reuses everything TV Manager already has configured: the
Newznab/Torznab providers, the NZB and torrent download clients, TMDb
credentials and the media servers. Nothing here needs its own setup beyond an
optional movie library folder, which is detected from Plex when possible.

Flow: library scan (what you already own) -> discovery (new digital/physical
releases from TMDb that pass your filters) -> search (indexers, movie
categories) -> handoff (your clients, movie category/label) -> polling
(completed, failed or stalled) -> import (Plex naming, media server scan).
Failed and stalled releases are blocklisted and the movie is searched again.
"""
import json
import os
import re
import shutil
import threading
import time
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import requests

import engine
import indexer_client

SECTION = 'Movies'
DEFAULTS = {
    'enabled': '1',
    'library_root': '',
    'detected_library_root': '',
    'download_dir': '',
    'auto_add': '1',
    'auto_grab': '1',
    'min_rating': '6.5',
    'min_votes': '150',
    'discovery_days': '120',
    'discovery_region': 'US',
    'languages': 'en',
    'exclude_genres': 'Documentary,TV Movie',
    'max_auto_add_per_run': '10',
    'max_searches_per_run': '10',
    'min_resolution': '720',
    'max_resolution': '1080',
    'cutoff_resolution': '1080',
    'allow_remux': '0',
    'allow_hevc': '1',
    'min_size_mb': '500',
    'max_size_gb': '40',
    'ignore_words': '',
    'preferred_words': '',
    'categories': '2000',
    'sab_category': 'movies',
    'torrent_label': 'movies',
    'nzbget_category': 'movies',
    'torrent_import_method': 'hardlink',
    'stalled_hours': '36',
    'library_scanned_at': '',
    'extra_library_folders': '',
    'last_scan_report': '',
    'destination_folders': '',
    'destination_rule': 'most_free',
    'min_free_gb': '50',
}
VIDEO_EXT = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.ts', '.m2ts', '.mpg', '.mpeg'}
SIDECAR_EXT = {'.srt', '.sub', '.idx', '.ass', '.ssa', '.vtt'}
PRE_RELEASE = {'cam', 'camrip', 'hdcam', 'ts', 'telesync', 'hdts', 'tc', 'telecine', 'scr', 'screener',
               'dvdscr', 'dvdscreener', 'r5', 'workprint', 'hdtc', 'pdvd', 'predvd'}
DISC_IMAGES = {'iso', 'bdmv', 'img'}
JOB_INTERVALS = {'movie_library_scan': 1440, 'movie_discovery': 720, 'movie_search': 60, 'movie_downloads': 10}
_movie_mode_unsupported = set()
PLEX_PAGE = 1000
_lock = threading.RLock()


# ---------------------------------------------------------------- settings / db

def cx(readonly=False):
    return engine.cx(readonly=readonly)


def setting(name):
    value = engine.get_setting(SECTION, name, None)
    return DEFAULTS.get(name, '') if value is None else value


def flag(name):
    return engine.as_bool(setting(name), False)


def number(name, default=0.0):
    try:
        return float(str(setting(name)).strip())
    except (TypeError, ValueError):
        return default


def now_iso():
    return engine.now_iso()


def simulation():
    return engine.as_bool(engine.get_setting('TVManager', 'simulation_mode', '0'), False)


def init():
    with cx() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS movies(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tmdb_id INTEGER UNIQUE,
          imdb_id TEXT,
          title TEXT NOT NULL,
          original_title TEXT,
          year INTEGER,
          overview TEXT,
          poster_path TEXT,
          release_date TEXT,
          available_date TEXT,
          genres TEXT,
          rating REAL,
          votes INTEGER,
          status TEXT NOT NULL DEFAULT 'Wanted',
          monitored INTEGER NOT NULL DEFAULT 1,
          quality TEXT,
          resolution INTEGER,
          file_path TEXT,
          size INTEGER,
          release_name TEXT,
          added_via TEXT DEFAULT 'manual',
          added_at TEXT DEFAULT CURRENT_TIMESTAMP,
          downloaded_at TEXT,
          last_search TEXT,
          search_count INTEGER DEFAULT 0,
          message TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_movies_status ON movies(status, monitored);
        CREATE INDEX IF NOT EXISTS idx_movies_imdb ON movies(imdb_id);
        CREATE INDEX IF NOT EXISTS idx_movies_title_year ON movies(title, year);
        CREATE TABLE IF NOT EXISTS movie_search_results(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          movie_id INTEGER NOT NULL,
          provider TEXT, protocol TEXT, title TEXT, url TEXT, guid TEXT,
          size INTEGER, seeders INTEGER, quality TEXT, resolution INTEGER,
          score REAL, rejected_reason TEXT, status TEXT DEFAULT 'Found',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_movie_results_movie ON movie_search_results(movie_id, status);
        CREATE TABLE IF NOT EXISTS movie_downloads(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          movie_id INTEGER NOT NULL,
          result_id INTEGER,
          client TEXT, provider TEXT, protocol TEXT, release_name TEXT, guid TEXT,
          external_id TEXT, url TEXT,
          status TEXT NOT NULL DEFAULT 'Queued',
          progress REAL DEFAULT 0,
          content_path TEXT,
          destination TEXT,
          is_upgrade INTEGER DEFAULT 0,
          message TEXT,
          created_at TEXT,
          updated_at TEXT,
          completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_movie_downloads_status ON movie_downloads(status);
        CREATE TABLE IF NOT EXISTS movie_blocklist(
          guid TEXT PRIMARY KEY,
          movie_id INTEGER,
          title TEXT,
          reason TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        for name, interval in JOB_INTERVALS.items():
            # Movie automation is on by default (the scheduler itself still
            # follows the global automation switch). A later manual disable
            # on the Jobs page is preserved.
            c.execute("INSERT OR IGNORE INTO scheduler_jobs(name,enabled,interval_minutes) VALUES(?,?,?)",
                      (name, 1, interval))
            # Same rule as the TV jobs: an interval saved in Settings > Automation wins.
            try:
                override = c.execute("SELECT value FROM settings WHERE lower(section)='tvmanager' AND name=?",
                                     ('job_interval_' + name,)).fetchone()
            except Exception:
                override = None
            if override and str(override[0] or '').strip().isdigit():
                c.execute('UPDATE scheduler_jobs SET interval_minutes=? WHERE name=?', (max(1, int(override[0])), name))
        c.commit()


def log(event, message, level='info', data=None):
    engine.log(event, message, level, data=data)


# ---------------------------------------------------------------- names and quality

def norm(text):
    t = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode().lower()
    t = t.replace('&', ' and ').replace("'", '').replace('’', '')
    t = re.sub(r'[^a-z0-9]+', ' ', t)
    return ' '.join(t.split())


def _year_token(token):
    if re.fullmatch(r'(19|20)\d\d', token):
        return 1900 <= int(token) <= date.today().year + 2
    return False


def parse_release(name):
    """Split a release or folder name into (title, year, remaining tokens)."""
    text = str(name or '')
    text = re.sub(r'\.(mkv|mp4|avi|m4v|mov|wmv|ts|m2ts|mpg|mpeg|nzb|torrent)$', '', text, flags=re.I)
    tokens = norm(text).split()
    positions = [i for i, tok in enumerate(tokens) if _year_token(tok) and i > 0]
    if not positions:
        return ' '.join(tokens), None, []
    at = positions[-1]
    return ' '.join(tokens[:at]), int(tokens[at]), tokens[at + 1:]


def _title_variants(title):
    base = norm(title)
    out = {base}
    if base.startswith('the '):
        out.add(base[4:])
    else:
        out.add('the ' + base)
    out.add(base.replace(' and ', ' '))
    return {x for x in out if x}


def release_rejection(release, movie):
    """Why a release title does not belong to this movie, or None when it does."""
    title, year, _rest = parse_release(release)
    if re.search(r'\bs\d{1,2}\s?e\d{1,3}\b', norm(release)):
        return 'Looks like a TV episode, not this movie'
    names = set()
    for candidate in (movie.get('title'), movie.get('original_title')):
        if candidate:
            names |= _title_variants(candidate)
    if title not in names and title.replace(' and ', ' ') not in names:
        return 'Not this movie (title does not match)'
    wanted = movie.get('year')
    if wanted and (year is None or abs(int(year) - int(wanted)) > 1):
        return f'Not this movie (year {year or "missing"}, expected {wanted})'
    return None


def resolution_of(title):
    t = norm(title).split()
    if '2160p' in t or '4k' in t or 'uhd' in t:
        return 2160
    if '1080p' in t or '1080i' in t:
        return 1080
    if '720p' in t:
        return 720
    return 480


def source_points(title):
    n = norm(title)
    t = set(n.split())
    if 'remux' in t:
        return 12
    if t & {'bluray', 'bdrip', 'brrip'} or 'blu ray' in n:
        return 10
    if t & {'webdl', 'web'} or 'web dl' in n:
        return 9
    if 'webrip' in t:
        return 7
    if 'hdtv' in t:
        return 4
    if 'dvdrip' in t:
        return 3
    return 0


def quality_label(title):
    return engine.infer_quality(title) or f'{resolution_of(title)}p'


def score_release(item, movie):
    """Return (score, rejection reason) for one indexer result."""
    title = item.get('title') or ''
    reason = release_rejection(title, movie)
    if reason:
        return -10000, reason
    _t, _y, rest = parse_release(title)
    rest_set = set(rest)
    if rest_set & PRE_RELEASE:
        return -10000, 'Cinema camera or screener copy'
    if rest_set & DISC_IMAGES or 'complete bluray' in ' '.join(rest):
        return -10000, 'Disc image, not a playable file'
    if '3d' in rest_set and '3d' not in norm(movie.get('title')).split():
        return -10000, '3D release'
    if 'remux' in rest_set and not flag('allow_remux'):
        return -10000, 'Remux releases are turned off'
    if rest_set & {'x265', 'h265', 'hevc'} and not flag('allow_hevc'):
        return -10000, 'HEVC releases are turned off'
    res = resolution_of(title)
    if res < number('min_resolution', 720):
        return -10000, f'Below minimum resolution ({int(number("min_resolution", 720))}p)'
    if res > number('max_resolution', 1080):
        return -10000, f'Above maximum resolution ({int(number("max_resolution", 1080))}p)'
    size = int(item.get('size') or 0)
    if size:
        if size < number('min_size_mb', 500) * 1024 * 1024:
            return -10000, f'Smaller than {int(number("min_size_mb", 500))} MB'
        if size > number('max_size_gb', 40) * 1024 ** 3:
            return -10000, f'Larger than {number("max_size_gb", 40):g} GB'
    lowered = ' ' + norm(title) + ' '
    ignored = engine.parse_words(engine.get_setting('General', 'ignore_words', '')) + engine.parse_words(setting('ignore_words'))
    for word in ignored:
        if word and f' {norm(word)} ' in lowered:
            return -10000, f'Ignored word: {word}'
    if item.get('protocol') == 'torrent':
        minimum = int(item.get('minimum_seeders') or 0)
        if int(item.get('seeders') or 0) < max(1, minimum):
            return -10000, 'Not enough seeders'
    score = {2160: 45, 1080: 35, 720: 25}.get(res, 10) + source_points(title)
    if rest_set & {'proper', 'repack'}:
        score += 5
    for index, word in enumerate(engine.parse_words(setting('preferred_words'))):
        if word and f' {norm(word)} ' in lowered:
            score += max(1, 10 - index)
    if item.get('protocol') == 'torrent':
        score += min(int(item.get('seeders') or 0), 200) / 100
    score -= int(item.get('priority') or 0) / 1000
    return score, None


# ---------------------------------------------------------------- providers and search

def _clients():
    cfg = engine.downloader_config_public()
    return cfg.get('nzb_method') or '', cfg.get('torrent_method') or ''


def providers():
    """Enabled indexers whose protocol has a configured download client."""
    import provider_manager
    import advanced
    nzb_method, torrent_method = _clients()
    out = []
    for p in engine.parse_newznab():
        if nzb_method and provider_manager.eligible(p, 'manual'):
            out.append(dict(p, protocol='nzb'))
    for p in advanced.provider_defs_raw():
        torrent = str(p.get('protocol') or '').lower() == 'torznab'
        if (torrent and torrent_method) or (not torrent and nzb_method):
            out.append(dict(p, protocol='torrent' if torrent else 'nzb'))
    return out


def parse_feed(root):
    items, seen = [], set()
    tag = indexer_client._tag
    for node in root.iter():
        if tag(node) != 'item':
            continue
        data = {tag(n): n.text or '' for n in node}
        attrs = {n.get('name'): n.get('value') for n in node.iter() if tag(n) == 'attr'}
        enclosure = next((n for n in node if tag(n) == 'enclosure'), None)
        link = (enclosure.get('url') if enclosure is not None else None) or data.get('link') or ''
        guid = data.get('guid') or link
        if not link or not guid or guid in seen:
            continue
        seen.add(guid)

        def whole(value):
            try:
                return max(0, int(value or 0))
            except (TypeError, ValueError):
                return 0
        items.append({'title': data.get('title', ''), 'url': link, 'guid': guid,
                      'size': whole((enclosure.get('length') if enclosure is not None else None) or attrs.get('size')),
                      'seeders': whole(attrs.get('seeders')), 'publish_date': data.get('pubDate')})
    return items


def search_provider(provider, movie, timeout=25):
    cats = str(setting('categories') or '2000')
    key = indexer_client.endpoint(provider['url'])
    imdb = str(movie.get('imdb_id') or '').lower().removeprefix('tt')
    queries = []
    if imdb.isdigit() and key not in _movie_mode_unsupported:
        queries.append(('id', {'t': 'movie', 'imdbid': imdb, 'cat': cats}))
    names = [movie['title']]
    if movie.get('original_title') and norm(movie['original_title']) != norm(movie['title']):
        names.append(movie['original_title'])
    for name in names:
        text = f"{name} {movie['year']}" if movie.get('year') else name
        queries.append(('text', {'t': 'search', 'q': text, 'cat': cats}))
    found, seen = [], set()
    for kind, params in queries:
        try:
            root = indexer_client.request_xml(provider, dict(params, extended='1', limit='100'), timeout)
        except indexer_client.IndexerError as error:
            if kind == 'id' and error.code in {200, 201, 202, 203}:
                _movie_mode_unsupported.add(key)
                continue
            raise
        batch = parse_feed(root)
        for item in batch:
            if item['guid'] in seen:
                continue
            seen.add(item['guid'])
            found.append(item)
        if kind == 'id' and batch:
            break
    return found


def _blocklisted(c, guids):
    rows = set()
    for guid in guids:
        if not guid:
            continue
        if c.execute('SELECT 1 FROM movie_blocklist WHERE guid=?', (guid,)).fetchone():
            rows.add(guid)
            continue
        try:
            if c.execute('SELECT 1 FROM failed_releases WHERE guid=? LIMIT 1', (guid,)).fetchone():
                rows.add(guid)
        except Exception:
            pass
    return rows


def get_movie(movie_id):
    with cx() as c:
        row = c.execute('SELECT * FROM movies WHERE id=?', (int(movie_id),)).fetchone()
    if not row:
        raise ValueError('Movie not found')
    return dict(row)


def _ensure_imdb(movie):
    if movie.get('imdb_id') or not movie.get('tmdb_id'):
        return movie
    try:
        imdb = tmdb(f"/movie/{movie['tmdb_id']}/external_ids").get('imdb_id')
        if imdb:
            with cx() as c:
                c.execute('UPDATE movies SET imdb_id=? WHERE id=?', (imdb, movie['id']))
                c.commit()
            movie['imdb_id'] = imdb
    except Exception:
        pass
    return movie


def search_movie(movie_id, auto_grab=False):
    import ops
    movie = _ensure_imdb(get_movie(movie_id))
    found, errors = [], []
    plist = providers()
    if not plist:
        errors.append('No indexers with a matching download client are configured.')
    for provider in plist:
        if not ops.provider_is_available(provider['name']):
            errors.append(f"{provider['name']}: temporarily suspended after repeated failures")
            continue
        started = time.perf_counter()
        try:
            for item in search_provider(provider, movie):
                item.update(provider=provider['name'], protocol=provider['protocol'],
                            priority=provider.get('priority') or 0, minimum_seeders=provider.get('minimum_seeders') or 0)
                found.append(item)
            ops.provider_result(provider['name'], True, (time.perf_counter() - started) * 1000)
        except Exception as error:
            ops.provider_result(provider['name'], False, (time.perf_counter() - started) * 1000, error)
            errors.append(f"{provider['name']}: {indexer_client.safe_error(error)}")
    current_res = int(movie.get('resolution') or 0) if movie.get('status') == 'Downloaded' else 0
    with cx() as c:
        blocked = _blocklisted(c, [r['guid'] for r in found])
    for item in found:
        score, reason = score_release(item, movie)
        if not reason and item['guid'] in blocked:
            score, reason = -10000, 'Previously failed or stalled'
        res = resolution_of(item['title'])
        if not reason and current_res and res <= current_res:
            score, reason = -10000, f'Not better than the current {current_res}p file'
        item.update(score=score, rejected_reason=reason, quality=quality_label(item['title']), resolution=res)
    found.sort(key=lambda r: (r['rejected_reason'] is not None, -r['score'], -(r['size'] or 0)))
    with cx() as c:
        c.execute("DELETE FROM movie_search_results WHERE movie_id=? AND status IN ('Found','Rejected')", (movie['id'],))
        for item in found:
            cur = c.execute("""INSERT INTO movie_search_results(movie_id,provider,protocol,title,url,guid,size,seeders,
                               quality,resolution,score,rejected_reason,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (movie['id'], item['provider'], item['protocol'], item['title'], item['url'], item['guid'],
                             item['size'], item['seeders'], item['quality'], item['resolution'], item['score'],
                             item['rejected_reason'], 'Rejected' if item['rejected_reason'] else 'Found'))
            item['id'] = cur.lastrowid
        c.execute("UPDATE movies SET last_search=?,search_count=COALESCE(search_count,0)+1 WHERE id=?", (now_iso(), movie['id']))
        c.commit()
    accepted = [r for r in found if not r['rejected_reason']]
    log('movie_search', f"Searched {movie['title']} ({movie.get('year') or '?'}): {len(accepted)} usable of {len(found)} results",
        data={'movie_id': movie['id'], 'errors': errors})
    grabbed = None
    if auto_grab and accepted and not simulation():
        try:
            grabbed = grab_result(accepted[0]['id'])
        except Exception as error:
            errors.append(f'Download handoff failed: {error}')
            log('movie_grab_error', f"{movie['title']}: {error}", 'warning')
    return {'movie_id': movie['id'], 'results': found, 'errors': errors, 'grabbed': grabbed}


# ---------------------------------------------------------------- download handoff

def _getter(section, name, default=None):
    if (section, name) == ('TORRENT', 'torrent_label'):
        return setting('torrent_label')
    return engine.get_setting(section, name, default)


def _send_sab(result):
    host = (engine.get_setting('SABnzbd', 'sab_host', '') or '').rstrip('/') + '/'
    params = {'mode': 'addurl', 'name': result['url'], 'nzbname': result['title'],
              'apikey': engine.get_setting('SABnzbd', 'sab_apikey', ''),
              'cat': setting('sab_category') or 'movies', 'output': 'json'}
    response = requests.get(urljoin(host, 'api'), params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    if not data.get('status'):
        raise ValueError(data.get('error') or 'SABnzbd rejected the NZB')
    ids = data.get('nzo_ids') or []
    if not ids:
        raise ValueError('SABnzbd accepted the request but did not return a tracking ID')
    return ids[0]


def _send_qbit(result):
    import torrent_metadata
    session, host = engine._qbit_session()
    torrent_id, payload = torrent_metadata.describe(result['url'])
    data = {} if payload else {'urls': result['url']}
    if setting('torrent_label'):
        data['category'] = setting('torrent_label')
    files = {'files': {'torrents': ('movie.torrent', payload, 'application/x-bittorrent')}} if payload else {}
    response = session.post(host + '/api/v2/torrents/add', data=data, timeout=15, **files)
    response.raise_for_status()
    if response.text.strip().lower() not in {'ok.', ''}:
        raise ValueError('qBittorrent rejected the torrent: ' + response.text[:200])
    return torrent_id


def _send_nzbget(result):
    from downloader_polling import nzb_rpc
    external = nzb_rpc(engine.get_setting, 'append', [result['title'] + '.nzb', result['url'], setting('nzbget_category') or 'movies',
                                                      0, False, False, '', 0, 'SCORE'])
    if type(external) is not int or external <= 0:
        raise ValueError('NZBGet did not accept the download')
    return str(external)


def handoff(result):
    """Send a release to the configured client for its protocol; returns (client, external id)."""
    import native_downloaders
    nzb_method, torrent_method = _clients()
    method = nzb_method if result['protocol'] == 'nzb' else torrent_method
    if method == 'sabnzbd':
        return 'SABnzbd', _send_sab(result)
    if method == 'nzbget':
        return 'NZBGet', _send_nzbget(result)
    if method == 'qbittorrent':
        return 'qBittorrent', _send_qbit(result)
    if method in native_downloaders.NAMES:
        return native_downloaders.NAMES[method], native_downloaders.run(method, _getter, 'send', result)
    if method == 'transmission':
        return 'Transmission', engine.send_transmission(result)
    if method == 'deluge':
        return 'Deluge', engine.send_deluge(result)
    if method == 'blackhole':
        return 'Blackhole', engine.send_blackhole(result)
    raise ValueError(f"No download client is configured for {result['protocol']} releases")


def grab_result(result_id):
    if not library_root():
        raise ValueError('Set the movie library folder in Movies > Settings before downloading.')
    with _lock:
        with cx() as c:
            row = c.execute("""SELECT r.*,m.title movie_title,m.year movie_year,m.status movie_status
                               FROM movie_search_results r JOIN movies m ON m.id=r.movie_id WHERE r.id=?""",
                            (int(result_id),)).fetchone()
            if not row:
                raise ValueError('Search result not found')
            row = dict(row)
            if row['rejected_reason']:
                raise ValueError('This result was rejected: ' + row['rejected_reason'])
            active = c.execute("SELECT id FROM movie_downloads WHERE movie_id=? AND status IN ('Queued','Downloading','Downloaded')",
                               (row['movie_id'],)).fetchone()
            if active:
                raise ValueError('This movie already has an active download.')
            if _blocklisted(c, [row['guid']]):
                raise ValueError('This release previously failed and is blocklisted.')
        client, external = handoff(row)
        stamp = now_iso()
        with cx() as c:
            cur = c.execute("""INSERT INTO movie_downloads(movie_id,result_id,client,provider,protocol,release_name,guid,external_id,url,
                               status,is_upgrade,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,'Queued',?,?,?)""",
                            (row['movie_id'], row['id'], client, row['provider'], row['protocol'], row['title'], row['guid'],
                             str(external or ''), row['url'], 1 if row['movie_status'] == 'Downloaded' else 0, stamp, stamp))
            c.execute("UPDATE movie_search_results SET status='Grabbed' WHERE id=?", (row['id'],))
            if row['movie_status'] != 'Downloaded':
                c.execute("UPDATE movies SET status='Snatched',release_name=?,message=NULL WHERE id=?", (row['title'], row['movie_id']))
            c.commit()
            download_id = cur.lastrowid
    log('movie_download_queued', f"Queued {row['movie_title']} ({row['movie_year'] or '?'}) in {client}: {row['title']}",
        data={'movie_id': row['movie_id'], 'download_id': download_id})
    try:
        import advanced
        advanced.fire_webhooks('snatched', {'movie': row['movie_title'], 'year': row['movie_year'], 'release': row['title'], 'client': client,
                                            'message': f"Movie snatched: {row['movie_title']} ({row['movie_year'] or '?'}) — {row['title']}"})
    except Exception:
        pass
    return {'ok': True, 'client': client, 'external_id': external, 'download_id': download_id}


# ---------------------------------------------------------------- client polling

def _sab_api(params, timeout=15):
    host = (engine.get_setting('SABnzbd', 'sab_host', '') or '').rstrip('/') + '/'
    response = requests.get(urljoin(host, 'api'), params=dict(params, output='json', apikey=engine.get_setting('SABnzbd', 'sab_apikey', '') or ''),
                            timeout=timeout)
    response.raise_for_status()
    return response.json()


def _sab_snapshot():
    out = {}
    for slot in (_sab_api({'mode': 'queue', 'limit': 500}).get('queue') or {}).get('slots') or []:
        try:
            progress = float(slot.get('percentage') or 0) / 100
        except (TypeError, ValueError):
            progress = 0
        out[str(slot.get('nzo_id'))] = {'status': 'Downloading', 'progress': progress}
    for slot in (_sab_api({'mode': 'history', 'limit': 300}).get('history') or {}).get('slots') or []:
        status = str(slot.get('status') or '').lower()
        nzo = str(slot.get('nzo_id'))
        if status in {'completed', 'success'}:
            out[nzo] = {'status': 'Downloaded', 'progress': 1, 'path': slot.get('storage') or ''}
        elif status == 'failed':
            out[nzo] = {'status': 'Failed', 'progress': 0, 'error': slot.get('fail_message') or 'SABnzbd reported a failure'}
        else:  # verifying, repairing, extracting, moving
            out[nzo] = {'status': 'Downloading', 'progress': 0.99}
    return out


def _qbit_snapshot():
    session, host = engine._qbit_session()
    response = session.get(host + '/api/v2/torrents/info', timeout=15)
    response.raise_for_status()
    out = {}
    for row in response.json():
        progress = float(row.get('progress') or 0)
        failed = row.get('state') in {'error', 'missingFiles'}
        out[str(row.get('hash')).lower()] = {'status': 'Failed' if failed else 'Downloaded' if progress >= 1 else 'Downloading',
                                             'progress': progress, 'path': row.get('content_path') or '',
                                             'error': 'qBittorrent reported an error' if failed else ''}
    return out


def _utorrent_snapshot():
    import native_downloaders
    out = {}
    with native_downloaders.UTorrent(_getter) as client:
        client.connect()
        for r in client.rpc({'list': 1}).get('torrents', []):
            state = native_downloaders.state(native_downloaders.ratio(r[4], 1000), failed=bool(int(r[1]) & 16))
            if len(r) > 26 and r[26]:
                # uTorrent/BitTorrent report the folder the torrent was saved in; for a single-file
                # torrent that is the parent folder, so the torrent name is added (as Sonarr does).
                save, name = str(r[26]), str(r[2] or '')
                state['path'] = save if not name or os.path.basename(save.rstrip('\\/')) == name else os.path.join(save, name)
            out[str(r[0]).lower()] = state
    return out


def snapshot(client):
    import native_downloaders
    import downloader_polling
    if client == 'SABnzbd':
        return _sab_snapshot()
    if client == 'qBittorrent':
        return _qbit_snapshot()
    if client == 'uTorrent':
        return _utorrent_snapshot()
    if client in {'NZBGet', 'Transmission', 'Deluge'}:
        return downloader_polling.snapshot(client, engine.get_setting)
    method = next((k for k, v in native_downloaders.NAMES.items() if v == client), None)
    if method:
        return native_downloaders.run(method, _getter, 'snapshot')
    return None  # Blackhole and unknown clients cannot be polled.


def _age_hours(stamp):
    try:
        return (datetime.now() - datetime.fromisoformat(str(stamp).replace('Z', '').replace(' ', 'T'))).total_seconds() / 3600
    except (TypeError, ValueError):
        return 0


def fail_download(download_id, reason):
    """Blocklist a release and put the movie back in the wanted list for another search."""
    with cx() as c:
        row = c.execute('SELECT * FROM movie_downloads WHERE id=?', (download_id,)).fetchone()
        if not row:
            return
        c.execute("UPDATE movie_downloads SET status='Failed',message=?,updated_at=? WHERE id=?", (reason, now_iso(), download_id))
        if row['guid']:
            c.execute('INSERT OR REPLACE INTO movie_blocklist(guid,movie_id,title,reason) VALUES(?,?,?,?)',
                      (row['guid'], row['movie_id'], row['release_name'], reason))
        c.execute("UPDATE movies SET status=CASE WHEN status='Downloaded' THEN status ELSE 'Wanted' END,last_search=NULL,message=? WHERE id=?",
                  (f'Last download failed: {reason}', row['movie_id']))
        c.commit()
    log('movie_download_failed', f"{row['release_name']}: {reason}. Blocklisted; the movie will be searched again.", 'warning')


def poll_downloads():
    with cx() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM movie_downloads WHERE status IN ('Queued','Downloading')").fetchall()]
    stalled_hours = number('stalled_hours', 36)
    snapshots, errors, changed = {}, [], 0
    for client in sorted({r['client'] for r in rows}):
        try:
            snapshots[client] = snapshot(client)
        except Exception as error:
            snapshots[client] = False
            errors.append(f'{client}: {str(error)[:200]}')
    for row in rows:
        states = snapshots.get(row['client'])
        external = str(row['external_id'] or '')
        state = (states or {}).get(external.lower()) or (states or {}).get(external)
        if state and state.get('status') == 'Failed':
            fail_download(row['id'], state.get('error') or 'Download client reported a failure')
            changed += 1
            continue
        if state and state.get('status') == 'Downloaded':
            with cx() as c:
                c.execute("UPDATE movie_downloads SET status='Downloaded',progress=1,content_path=?,completed_at=?,updated_at=? WHERE id=?",
                          (state.get('path') or row['content_path'], now_iso(), now_iso(), row['id']))
                c.commit()
            changed += 1
            continue
        if state:
            with cx() as c:
                c.execute("UPDATE movie_downloads SET status='Downloading',progress=?,updated_at=? WHERE id=?",
                          (float(state.get('progress') or 0), now_iso(), row['id']))
                c.commit()
        # A client that could not be reached right now (False) is not evidence of a stall.
        if states is not False and _age_hours(row['created_at']) >= stalled_hours:
            progress = int(float((state or {}).get('progress') or row.get('progress') or 0) * 100)
            fail_download(row['id'], f'Stalled: not complete after {stalled_hours:g} hours ({progress}% done)')
            changed += 1
    return {'checked': len(rows), 'changed': changed, 'errors': errors}


# ---------------------------------------------------------------- import / organize

def _map(path):
    try:
        import ops
        return ops.map_path(path)
    except Exception:
        return path


def _sab_complete_dirs():
    if not (engine.get_setting('SABnzbd', 'sab_host', '') or '').strip():
        return []
    try:
        config = _sab_api({'mode': 'get_config'}, timeout=10).get('config') or {}
    except Exception:
        return []
    base = (config.get('misc') or {}).get('complete_dir') or ''
    out = [base] if base else []
    for cat in config.get('categories') or []:
        folder = cat.get('dir') or ''
        if folder:
            out.append(folder if os.path.isabs(folder) or folder.startswith('\\\\') else os.path.join(base, folder))
    return out


def download_roots():
    roots = [setting('download_dir'), engine.get_setting('General', 'tv_download_dir', ''),
             engine.get_setting('TORRENT', 'torrent_path', ''), *_sab_complete_dirs()]
    out = []
    for root in roots:
        root = _map(str(root or '').strip())
        if root and os.path.isdir(root) and root not in out:
            out.append(root)
    return out


def _videos(path):
    path = Path(path)
    if path.is_file():
        return [path] if path.suffix.lower() in VIDEO_EXT else []
    found = []
    for item in path.rglob('*'):
        if item.is_file() and item.suffix.lower() in VIDEO_EXT and not re.search(r'(^|[\W_])sample([\W_]|$)', item.name, re.I):
            found.append(item)
    return sorted(found, key=lambda p: p.stat().st_size, reverse=True)


def locate(download):
    """Find the completed files of a download on disk."""
    hint = str(download.get('content_path') or '').strip()
    roots = {_same(r) for r in download_roots()}
    if hint:
        mapped = _map(hint)
        joined = os.path.join(mapped, download.get('release_name') or '')
        if os.path.exists(mapped) and _same(mapped) not in roots:
            return Path(mapped)
        if os.path.exists(joined):
            return Path(joined)
    wanted = norm(download.get('release_name'))
    if not wanted:
        return None
    for root in download_roots():
        try:
            level1 = list(Path(root).iterdir())
        except OSError:
            continue
        candidates = list(level1)
        for item in level1:
            # One level deeper covers category folders such as complete\movies.
            if item.is_dir() and norm(item.name) != wanted:
                try:
                    candidates.extend(item.iterdir())
                except OSError:
                    pass
        for item in candidates:
            name = item.stem if item.is_file() else item.name
            if norm(name) == wanted:
                return item
    return None


def _same(path):
    return os.path.normcase(os.path.normpath(str(path))).rstrip('\\/')


def safe_name(text):
    import naming
    return naming.safe_component(text).strip(' .') or 'Movie'


def movie_folder_name(movie):
    return safe_name(f"{movie['title']} ({movie['year']})" if movie.get('year') else movie['title'])


def _place(source, destination, method):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if method == 'move':
        shutil.move(str(source), str(destination))
        return 'move'
    if method == 'hardlink':
        try:
            os.link(source, destination)
            return 'hardlink'
        except OSError:
            pass
    shutil.copy2(source, destination)
    return 'copy'


def _trash_existing(path):
    """Move a replaced movie file to the trash on its own share (restorable from the Trash page)."""
    try:
        import trash
        root = library_root()
        fallback = Path(_map(root)) / trash.FOLDER_NAME if root else None
        return trash.move_to_trash(path, 'upgrades', reason='Movie replaced by an upgrade', fallback_root=fallback)
    except Exception:
        pass
    try:
        import app_paths
        trash = app_paths.application_root() / 'managed_trash' / 'movies' / datetime.now().strftime('%Y%m%d-%H%M%S')
        trash.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(trash / Path(path).name))
        return str(trash / Path(path).name)
    except Exception:
        return None


def import_download(download, dry_run=False):
    movie = get_movie(download['movie_id'])
    if not destination_folders():
        return {'ok': False, 'message': 'No movie destination folder is set (Movies > Settings)'}
    source = locate(download)
    if not source:
        return {'ok': False, 'message': 'Completed download not found in the download folders yet'}
    videos = _videos(source)
    if not videos:
        return {'ok': False, 'message': f'No video file found in {source}'}
    video = videos[0]
    try:
        size_needed = video.stat().st_size
    except OSError:
        size_needed = 0
    root, why = destination_for(movie, 0 if download.get('protocol') != 'nzb' and setting('torrent_import_method') == 'hardlink' else size_needed)
    if not root:
        return {'ok': False, 'message': why}
    folder = Path(_map(root)) / movie_folder_name(movie)
    target = folder / (movie_folder_name(movie) + video.suffix.lower())
    method = 'move' if download.get('protocol') == 'nzb' else (setting('torrent_import_method') or 'hardlink')
    plan = {'ok': True, 'source': str(video), 'destination': str(target), 'method': method}
    if dry_run:
        return dict(plan, dry_run=True)
    replaced = None
    old = movie.get('file_path')
    if target.exists():
        replaced = _trash_existing(target)
    elif old and os.path.exists(_map(old)) and Path(_map(old)).resolve() != target.resolve():
        replaced = _trash_existing(_map(old))
    used = _place(video, target, method)
    if video.parent.exists():
        for sidecar in [p for p in video.parent.iterdir() if p.is_file() and p.suffix.lower() in SIDECAR_EXT]:
            suffix = sidecar.name[len(video.stem):] if sidecar.name.startswith(video.stem) else sidecar.suffix
            try:
                _place(sidecar, folder / (movie_folder_name(movie) + suffix), 'move' if used == 'move' else 'copy')
            except OSError:
                pass
    if used == 'move' and source.is_dir():
        roots = [Path(r).resolve() for r in download_roots()]
        resolved = source.resolve()
        if any(resolved != r and r in resolved.parents for r in roots) and not _videos(source):
            shutil.rmtree(source, ignore_errors=True)
    size = target.stat().st_size if target.exists() else None
    with cx() as c:
        c.execute("""UPDATE movies SET status='Downloaded',file_path=?,quality=?,resolution=?,size=?,release_name=?,
                     downloaded_at=?,message=NULL WHERE id=?""",
                  (str(target), quality_label(download['release_name']), resolution_of(download['release_name']), size,
                   download['release_name'], now_iso(), movie['id']))
        c.execute("UPDATE movie_downloads SET status='Completed',destination=?,updated_at=?,message=? WHERE id=?",
                  (str(target), now_iso(), f'Imported by {used} to {target}', download['id']))
        c.commit()
    scans = refresh_media_servers(str(folder))
    plex_note = _scan_note(scans, root)
    failed = any(not x.get('ok') for x in scans or [])
    log('movie_imported', f"Imported {movie['title']} ({movie.get('year') or '?'}) to {target} by {used}. {plex_note}",
        'warning' if failed else 'info',
        data={'movie_id': movie['id'], 'replaced': replaced, 'media_servers': scans, 'destination': root})
    try:
        import advanced
        advanced.fire_webhooks('downloaded', {'movie': movie['title'], 'year': movie.get('year'), 'path': str(target),
                                               'message': f"Movie added to Plex: {movie['title']} ({movie.get('year') or '?'})"})
    except Exception:
        pass
    return dict(plan, method=used, replaced=replaced)


def _scan_note(scans, root=None):
    if not scans:
        return 'No media server is set up to tell.'
    parts = []
    for s in scans:
        if not s.get('ok'):
            parts.append(f"{s.get('server')}: scan request failed")
        elif s.get('targeted'):
            parts.append(f"{s.get('server')}: scanned {s.get('path') or 'the movie folder'}")
        elif s.get('kind') == 'plex':
            n = s.get('refreshed')
            parts.append(f"{s.get('server')}: scanning {n} movie librar{'y' if n == 1 else 'ies'}" if n else f"{s.get('server')}: scanning its movie libraries")
        else:
            parts.append(f"{s.get('server')}: library refresh requested")
    return 'Media servers — ' + '; '.join(parts) + '.'


def import_completed(dry_run=None):
    dry_run = simulation() if dry_run is None else dry_run
    with cx() as c:
        rows = [dict(r) for r in c.execute("""SELECT * FROM movie_downloads WHERE status='Downloaded'
                                              OR (client='Blackhole' AND status IN ('Queued','Downloading')) ORDER BY id""").fetchall()]
    out = []
    for row in rows:
        try:
            if row['client'] == 'Blackhole':
                # No client to ask, so only take files that have not changed for 10 minutes.
                source = locate(row)
                if not source or time.time() - max((p.stat().st_mtime for p in [source, *_videos(source)]), default=0) < 600:
                    continue
            result = import_download(row, dry_run=dry_run)
        except Exception as error:
            result = {'ok': False, 'message': f'Import failed: {str(error)[:300]}'}
            log('movie_import_error', f"{row['release_name']}: {error}", 'warning')
        if not result.get('ok') and not dry_run:
            with cx() as c:
                c.execute('UPDATE movie_downloads SET message=?,updated_at=? WHERE id=?', (result.get('message'), now_iso(), row['id']))
                c.commit()
        out.append(dict(result, download_id=row['id'], release=row['release_name']))
    return {'checked': len(rows), 'imported': sum(1 for r in out if r.get('ok') and not r.get('dry_run')), 'items': out, 'dry_run': dry_run}


def refresh_media_servers(path):
    import advanced
    results = []
    for server in advanced.media_servers():
        if not server.get('enabled'):
            continue
        try:
            if str(server.get('kind') or '').lower() == 'plex':
                # Each Plex server already knows its movie libraries and their folders, so ask it to
                # scan all of them. Plex only picks up new or changed files, so this stays quick.
                result = advanced._refresh_plex(advanced.media_server(server['id'], masked=False), None,
                                                tv_only=False, section_type='movie')
            else:
                result = advanced.refresh_media_server(server['id'])
            results.append({'server': server['name'], **result})
        except Exception:
            results.append({'server': server['name'], 'ok': False, 'message': 'Media server scan request failed'})
    return results


# ---------------------------------------------------------------- library

def _plex_video(video):
    ids = {}
    for guid in [video.get('guid') or ''] + [g.get('id') or '' for g in video.findall('Guid')]:
        m = re.match(r'(?:com\.plexapp\.agents\.)?(tmdb|imdb|themoviedb)://(tt\d+|\d+)', guid)
        if m:
            ids['imdb' if m.group(2).startswith('tt') else 'tmdb'] = m.group(2)
    part = video.find('.//Part')
    year = video.get('year') or ''
    return {'title': video.get('title'), 'year': int(year) if year.isdigit() else None,
            'tmdb_id': int(ids['tmdb']) if ids.get('tmdb', '').isdigit() else None, 'imdb_id': ids.get('imdb'),
            'file': part.get('file') if part is not None else None,
            'size': int(part.get('size')) if part is not None and (part.get('size') or '').isdigit() else None}


def _plex_movies():
    """Every movie in every movie library of every enabled Plex server.

    Returns (movies, library folder paths, per-library report). Libraries are read
    page by page so very large libraries are complete; a server or library that
    cannot be read is reported, never silently skipped."""
    import advanced
    out, locations, sources = [], [], []
    for server in advanced.media_servers():
        if not server.get('enabled') or str(server.get('kind') or '').lower() != 'plex':
            continue
        try:
            full = advanced.media_server(server['id'], masked=False)
            base = full['url'].rstrip('/')
            headers = {'X-Plex-Token': full['token'], 'Accept': 'application/xml'}
            sections = ET.fromstring(requests.get(base + '/library/sections', headers=headers, timeout=15).content)
        except Exception as error:
            sources.append({'kind': 'plex', 'server': server.get('name'), 'library': None, 'locations': [], 'count': 0,
                            'ok': False, 'error': f'Could not reach this Plex server ({str(error)[:150]})'})
            log('movie_plex_index_error', f"{server.get('name')}: could not read Plex movie libraries ({str(error)[:120]})", 'warning')
            continue
        for directory in sections.findall('.//Directory'):
            if directory.get('type') != 'movie':
                continue
            paths = [loc.get('path') for loc in directory.findall('Location') if loc.get('path')]
            locations.extend(paths)
            entry = {'kind': 'plex', 'server': server.get('name'), 'library': directory.get('title'), 'locations': paths,
                     'count': 0, 'ok': True, 'error': ''}
            try:
                start = 0
                while True:
                    page = ET.fromstring(requests.get(f"{base}/library/sections/{directory.get('key')}/all", headers=headers,
                                                      params={'includeGuids': 1, 'X-Plex-Container-Start': start,
                                                              'X-Plex-Container-Size': PLEX_PAGE}, timeout=120).content)
                    videos = page.findall('.//Video')
                    out.extend(_plex_video(v) for v in videos)
                    entry['count'] += len(videos)
                    start += len(videos)
                    total = int(page.get('totalSize') or 0)
                    if not videos or len(videos) < PLEX_PAGE or (total and start >= total):
                        break
            except Exception as error:
                entry.update(ok=False, error=f'Could not read the whole library ({str(error)[:150]})')
                log('movie_plex_index_error', f"{server.get('name')} / {directory.get('title')}: {str(error)[:120]}", 'warning')
            sources.append(entry)
    return out, locations, sources


def _split_folders(text):
    return [p.strip().strip('"') for p in re.split(r'[\r\n;|]+', str(text or '')) if p.strip().strip('"')]


def library_folders(plex_locations=()):
    """All movie folders to read from disk: the import folder, extra folders and every Plex movie library folder."""
    out, seen = [], []
    candidates = [(p, 'Movie destination folder') for p in destination_folders()]
    candidates += [(p, 'Other movie folder') for p in _split_folders(setting('extra_library_folders'))]
    candidates += [(p, 'Plex library folder') for p in plex_locations or []]
    candidates += [(setting('detected_library_root'), 'Detected from Plex')]
    for raw, label in candidates:
        if not raw:
            continue
        mapped = _map(str(raw))
        key = os.path.normcase(os.path.normpath(mapped))
        if key in seen:
            continue
        seen.append(key)
        out.append({'path': mapped, 'configured': str(raw), 'source': label, 'reachable': os.path.isdir(mapped)})
    # A folder inside another listed folder is read with its parent.
    reachable = [os.path.normcase(os.path.normpath(f['path'])) for f in out if f['reachable']]
    for folder in out:
        key = os.path.normcase(os.path.normpath(folder['path']))
        folder['inside'] = next((p for p in reachable if p != key and key.startswith(p.rstrip('\\/') + os.sep)), None)
    return out


def _movie_from_name(name):
    match = re.match(r'^(.*?)\s*[\(\[](\d{4})[\)\]]', name)
    if match:
        return match.group(1).strip(' .-_'), int(match.group(2))
    title, year, _rest = parse_release(name)
    return title, year


def _scan_folder(root):
    """Movies in one library folder: Title (Year) folders, loose video files, and one level of grouping folders (A-Z, genres)."""
    items = []

    def add(name, video, path):
        title, year = _movie_from_name(name)
        if not title:
            return
        ids = re.search(r'tmdb-?(\d+)', path.name)
        imdb = re.search(r'(tt\d{6,})', path.name)
        items.append({'title': title, 'year': year, 'file': str(video), 'size': video.stat().st_size,
                      'tmdb_id': int(ids.group(1)) if ids else None, 'imdb_id': imdb.group(1) if imdb else None, 'source': 'library'})

    def visit(folder, depth):
        try:
            entries = sorted(Path(folder).iterdir())
        except OSError:
            return
        for entry in entries:
            if entry.name.startswith(('.', '@', '$', '#')) or entry.name.lower() in {'system volume information', 'recycler', 'lost+found'}:
                continue  # trash, NAS system folders and hidden folders are not movies
            try:
                if entry.is_file():
                    if entry.suffix.lower() in VIDEO_EXT and not re.search(r'(^|[\W_])sample([\W_]|$)', entry.name, re.I):
                        add(entry.stem, entry, entry)
                    continue
                if not entry.is_dir():
                    continue
                direct = [p for p in entry.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXT]
                _title, year = _movie_from_name(entry.name)
                if direct or year:
                    videos = _videos(entry)
                    if videos:
                        add(entry.name, videos[0], entry)
                elif depth == 0:
                    visit(entry, 1)  # e.g. Movies\A\Title (Year) or Movies\Action\Title (Year)
            except OSError:
                continue
    visit(root, 0)
    return items


def detect_library_root(plex_locations=None):
    if plex_locations is None:
        _items, plex_locations, _sources = _plex_movies()
    for location in plex_locations or []:
        mapped = _map(location)
        if mapped and os.path.isdir(mapped):
            return mapped
    if plex_locations:
        # Plex has movie libraries but none of their folders is reachable from this server:
        # a guessed folder would be one Plex never scans, so leave it for the user to set.
        return ''
    import library_destinations
    for root in library_destinations.library_roots(engine.get_setting('General', 'root_dirs', '')):
        parent = Path(_map(str(root))).parent
        for name in ('Movies', 'movies', 'Films'):
            if (parent / name).is_dir():
                return str(parent / name)
    return ''


def destination_folders():
    """Folders new movies go to, written the way THIS server reaches them (drive letter or UNC).

    They are configured here and never taken from a Plex server's library paths, because each
    Plex server may name the same folder differently. Older installs used one library_root."""
    folders = _split_folders(setting('destination_folders'))
    if not folders:
        legacy = (setting('library_root') or setting('detected_library_root') or '').strip()
        folders = [legacy] if legacy else []
    return folders


def library_root():
    folders = destination_folders()
    return folders[0] if folders else ''


def _free_gb(path):
    try:
        return shutil.disk_usage(path).free / 1024 ** 3
    except OSError:
        return None


def destination_status():
    out = []
    for folder in destination_folders():
        mapped = _map(folder)
        reachable = os.path.isdir(mapped)
        usage = None
        if reachable:
            try:
                usage = shutil.disk_usage(mapped)
            except OSError:
                usage = None
        out.append({'path': folder, 'reachable': reachable,
                    'free_gb': round(usage.free / 1024 ** 3, 1) if usage else None,
                    'total_gb': round(usage.total / 1024 ** 3, 1) if usage else None})
    return out


def destination_for(movie, size_bytes=0):
    """Pick the destination folder for a movie: the folder it already lives in (upgrades stay
    on the same drive), else the folder with the most free space, or the first with enough
    space when the rule is 'in_order'. Returns (folder, reason)."""
    folders = destination_folders()
    if not folders:
        return None, 'No movie destination folder is set (Movies > Settings)'
    old = (movie or {}).get('file_path')
    if old:
        for folder in folders:
            if _inside(_map(old), _map(folder)) and os.path.isdir(_map(folder)):
                return folder, 'same folder as the current copy'
    size_gb = (size_bytes or 0) / 1024 ** 3
    need = number('min_free_gb', 50) + size_gb
    reachable = []
    for index, folder in enumerate(folders):
        mapped = _map(folder)
        if os.path.isdir(mapped):
            free = _free_gb(mapped)
            reachable.append((index, free if free is not None else float('inf'), folder))
    if not reachable:
        return None, 'None of the movie destination folders can be reached from this server'
    # Folders keeping the free-space reserve come first; when every drive is below the reserve,
    # the movie still goes to the folder with the most room as long as it fits.
    candidates = [c for c in reachable if c[1] >= need]
    if not candidates:
        roomiest = max(reachable, key=lambda c: (c[1], -c[0]))
        if roomiest[1] < size_gb + 1:
            return None, f'No movie destination folder has room for this movie ({size_gb:.1f} GB)'
        return roomiest[2], 'most free space (every folder is below the free-space reserve)'
    if (setting('destination_rule') or 'most_free') == 'in_order':
        chosen = min(candidates)
    else:
        chosen = max(candidates, key=lambda c: (c[1], -c[0]))
    return chosen[2], 'first folder with space' if setting('destination_rule') == 'in_order' else 'most free space'


def _inside(child, parent):
    c, p = _same(child).replace('\\', '/'), _same(parent).replace('\\', '/')
    return bool(p) and (c == p or c.startswith(p + '/'))


def plex_movie_folders(locations=None):
    """Plex movie library folders as Plex names them and as this server reaches them."""
    if locations is None:
        report = last_scan_report()
        locations = [loc for s in report.get('sources', []) if s.get('kind') == 'plex' for loc in s.get('locations') or []]
    out = []
    for location in locations or []:
        mapped = _map(location)
        out.append({'plex_path': location, 'path': mapped, 'reachable': bool(mapped) and os.path.isdir(mapped)})
    return out


def library_plex_status(root=None, folders=None):
    """Whether new movies land inside a Plex movie library: 'ok', 'outside', 'no_plex' or 'unknown'."""
    root = library_root() if root is None else root
    folders = plex_movie_folders() if folders is None else folders
    if not root:
        return 'unknown'
    if not folders:
        report = last_scan_report()
        plex_seen = any(s.get('kind') == 'plex' for s in report.get('sources', []))
        return 'unknown' if not report else ('outside' if plex_seen else 'no_plex')
    mapped_root = _map(root)
    return 'ok' if any(_inside(mapped_root, f['path']) or _inside(root, f['plex_path']) for f in folders) else 'outside'


def _upsert_owned(c, item, index):
    key = (norm(item['title']), item.get('year'))
    existing = None
    if item.get('tmdb_id'):
        existing = c.execute('SELECT * FROM movies WHERE tmdb_id=?', (item['tmdb_id'],)).fetchone()
    if not existing and item.get('imdb_id'):
        existing = c.execute('SELECT * FROM movies WHERE imdb_id=?', (item['imdb_id'],)).fetchone()
    if not existing and key in index:
        existing = c.execute('SELECT * FROM movies WHERE id=?', (index[key],)).fetchone()
    res = resolution_of(item['file']) if item.get('file') else None
    if existing:
        if existing['status'] != 'Downloaded':
            c.execute("""UPDATE movies SET status='Downloaded',file_path=COALESCE(?,file_path),size=COALESCE(?,size),
                         resolution=COALESCE(resolution,?),downloaded_at=COALESCE(downloaded_at,?),message='Found in library' WHERE id=?""",
                      (item.get('file'), item.get('size'), res, now_iso(), existing['id']))
            return 'updated'
        if item.get('tmdb_id') and not existing['tmdb_id']:
            if not c.execute('SELECT 1 FROM movies WHERE tmdb_id=?', (item['tmdb_id'],)).fetchone():
                c.execute('UPDATE movies SET tmdb_id=?,imdb_id=COALESCE(imdb_id,?) WHERE id=?',
                          (item['tmdb_id'], item.get('imdb_id'), existing['id']))
        return 'known'
    cur = c.execute("""INSERT INTO movies(tmdb_id,imdb_id,title,year,status,monitored,file_path,size,resolution,added_via,downloaded_at)
                       VALUES(?,?,?,?,'Downloaded',1,?,?,?,?,?)""",
                    (item.get('tmdb_id'), item.get('imdb_id'), item['title'], item.get('year'), item.get('file'), item.get('size'),
                     res, item.get('source', 'library'), now_iso()))
    index[key] = cur.lastrowid
    return 'added'


def scan_library():
    plex, locations, sources = _plex_movies()
    detected = detect_library_root(locations)
    if detected != setting('detected_library_root'):
        engine.set_setting(SECTION, 'detected_library_root', detected)
    counts = {'plex': len(plex), 'folders': 0, 'added': 0, 'updated': 0}
    folder_items = []
    for folder in library_folders(locations):
        entry = {'kind': 'folder', 'path': folder['configured'], 'source': folder['source'], 'count': 0, 'ok': True, 'error': ''}
        if not folder['reachable'] and folder['source'] in {'Plex library folder', 'Detected from Plex'}:
            # Plex already listed these movies; the folder is only unreachable from this server.
            entry.update(error='Covered by the Plex library list (folder not reachable from this server)')
        elif not folder['reachable']:
            entry.update(ok=False, error='Not reachable from the TV Manager server (check the drive, share or Settings > Path Mappings)')
        elif folder['inside']:
            entry.update(error=f"Read with {folder['inside']}")
        else:
            found = _scan_folder(folder['path'])
            entry['count'] = len(found)
            folder_items.extend(found)
        sources.append(entry)
    counts['folders'] = len(folder_items)
    with cx() as c:
        index = {(norm(r['title']), r['year']): r['id'] for r in c.execute('SELECT id,title,year FROM movies').fetchall()}
        for item in [dict(p, source='plex') for p in plex if p.get('title')] + folder_items:
            outcome = _upsert_owned(c, item, index)
            if outcome in counts:
                counts[outcome] += 1
        owned = c.execute("SELECT COUNT(*) FROM movies WHERE status='Downloaded'").fetchone()[0]
        c.commit()
    plex_problems = [s for s in sources if s['kind'] == 'plex' and not s['ok']]
    report = {'scanned_at': now_iso(), 'complete': not plex_problems, 'owned': owned, 'sources': sources,
              'plex_movies': counts['plex'], 'folder_movies': counts['folders']}
    engine.set_setting(SECTION, 'last_scan_report', json.dumps(report))
    engine.set_setting(SECTION, 'library_scanned_at', now_iso())
    level = 'warning' if plex_problems or any(not s['ok'] for s in sources) else 'info'
    log('movie_library_scan', f"Movie library scan: {counts['plex']} in {sum(1 for s in sources if s['kind'] == 'plex' and s['library'])} Plex "
                              f"libraries, {counts['folders']} in {sum(1 for s in sources if s['kind'] == 'folder' and s['count'])} folders; "
                              f"{owned} owned in total; {counts['added']} new, {counts['updated']} marked downloaded"
                              + (f"; {len(plex_problems)} Plex library problem(s)" if plex_problems else ''), level, data=counts)
    return dict(counts, owned=owned, complete=report['complete'], library_root=library_root(), detected_library_root=detected,
                sources=sources)


def last_scan_report():
    try:
        return json.loads(setting('last_scan_report') or '{}')
    except ValueError:
        return {}


# ---------------------------------------------------------------- TMDb discovery

def tmdb(path, params=None):
    import tmdb_client
    return tmdb_client.get(path, params=params or {}, db_path=engine.DB, timeout=20)


_genres = {}


def genre_ids():
    if not _genres:
        for g in tmdb('/genre/movie/list').get('genres', []):
            _genres[g['name'].lower()] = g['id']
    return _genres


def available_date(details, region='US'):
    """Earliest digital or physical release date (the region first, then anywhere)."""
    best_region, best_any = None, None
    for country in (details.get('release_dates') or {}).get('results', []):
        for item in country.get('release_dates', []):
            if item.get('type') not in (4, 5):
                continue
            day = str(item.get('release_date') or '')[:10]
            if not day:
                continue
            if country.get('iso_3166_1') == region and (best_region is None or day < best_region):
                best_region = day
            if best_any is None or day < best_any:
                best_any = day
    return best_region or best_any


def is_available(movie):
    today = date.today().isoformat()
    if movie.get('available_date'):
        return movie['available_date'] <= today
    released = movie.get('release_date')
    if released:
        try:
            return (date.fromisoformat(released[:10]) + timedelta(days=90)).isoformat() <= today
        except ValueError:
            return True
    return bool(movie.get('year')) and int(movie['year']) < date.today().year


def _year(value):
    return int(value[:4]) if str(value or '')[:4].isdigit() else None


def add_movie(tmdb_id, added_via='manual', monitored=True):
    tmdb_id = int(tmdb_id)
    with cx() as c:
        existing = c.execute('SELECT * FROM movies WHERE tmdb_id=?', (tmdb_id,)).fetchone()
    if existing:
        if added_via == 'manual' and existing['status'] == 'Ignored':
            with cx() as c:
                c.execute("UPDATE movies SET status='Wanted',monitored=1,message=NULL,last_search=NULL WHERE id=?", (existing['id'],))
                c.commit()
            return {'created': False, 'movie': get_movie(existing['id'])}
        return {'created': False, 'movie': dict(existing)}
    details = tmdb(f'/movie/{tmdb_id}', {'append_to_response': 'release_dates,external_ids'})
    year = _year(details.get('release_date'))
    imdb = (details.get('external_ids') or {}).get('imdb_id') or details.get('imdb_id')
    with cx() as c:
        owned = None
        if imdb:
            owned = c.execute('SELECT * FROM movies WHERE imdb_id=? AND tmdb_id IS NULL', (imdb,)).fetchone()
        owned = owned or c.execute('SELECT * FROM movies WHERE tmdb_id IS NULL AND lower(title)=lower(?) AND year IS ?',
                                   (details.get('title') or '', year)).fetchone()
        if owned:
            c.execute('UPDATE movies SET tmdb_id=?,imdb_id=COALESCE(imdb_id,?),poster_path=COALESCE(poster_path,?),overview=COALESCE(overview,?) WHERE id=?',
                      (tmdb_id, imdb, details.get('poster_path'), details.get('overview'), owned['id']))
            c.commit()
            return {'created': False, 'movie': get_movie(owned['id'])}
        cur = c.execute("""INSERT INTO movies(tmdb_id,imdb_id,title,original_title,year,overview,poster_path,release_date,available_date,
                           genres,rating,votes,status,monitored,added_via) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'Wanted',?,?)""",
                        (tmdb_id, imdb, details.get('title') or 'Untitled', details.get('original_title'), year, details.get('overview'),
                         details.get('poster_path'), details.get('release_date'), available_date(details, setting('discovery_region') or 'US'),
                         ', '.join(g['name'] for g in details.get('genres') or []), details.get('vote_average'), details.get('vote_count'),
                         1 if monitored else 0, added_via))
        c.commit()
        movie_id = cur.lastrowid
    log('movie_added', f"Added {details.get('title')} ({year or '?'}) to Movies ({added_via})", data={'movie_id': movie_id, 'tmdb_id': tmdb_id})
    return {'created': True, 'movie': get_movie(movie_id)}


def discover_params(page=1):
    today = date.today()
    params = {'sort_by': 'popularity.desc', 'with_release_type': '4|5', 'region': setting('discovery_region') or 'US',
              'release_date.gte': (today - timedelta(days=int(number('discovery_days', 120)))).isoformat(),
              'release_date.lte': today.isoformat(), 'vote_average.gte': number('min_rating', 6.5),
              'vote_count.gte': int(number('min_votes', 150)), 'include_adult': 'false', 'page': page}
    languages = [x.strip() for x in str(setting('languages') or '').split(',') if x.strip()]
    if languages:
        params['with_original_language'] = '|'.join(languages)
    excluded = [x.strip().lower() for x in str(setting('exclude_genres') or '').split(',') if x.strip()]
    if excluded:
        ids = genre_ids()
        params['without_genres'] = ','.join(str(ids[name]) for name in excluded if name in ids)
    return params


def discover_auto():
    if not flag('auto_add'):
        return {'skipped': 'Automatic adding is turned off', 'added': 0}
    _require_library_scan()
    report = last_scan_report()
    if report and not report.get('complete', True):
        bad = ', '.join(f"{s.get('server')}{' / ' + s['library'] if s.get('library') else ''}" for s in report.get('sources', [])
                        if s.get('kind') == 'plex' and not s.get('ok'))
        return {'skipped': f'Not adding movies: the last library scan could not read {bad}, so owned movies there are unknown', 'added': 0}
    limit = int(number('max_auto_add_per_run', 10))
    added, seen, errors = [], 0, []
    for page in range(1, 4):
        if len(added) >= limit:
            break
        data = tmdb('/discover/movie', discover_params(page))
        for item in data.get('results', []):
            if len(added) >= limit:
                break
            seen += 1
            with cx() as c:
                known = c.execute('SELECT 1 FROM movies WHERE tmdb_id=? OR (lower(title)=lower(?) AND year IS ?)',
                                  (item['id'], item.get('title') or '', _year(item.get('release_date')))).fetchone()
            if known:
                continue
            try:
                result = add_movie(item['id'], added_via='auto')
                if result['created']:
                    added.append(result['movie']['title'])
            except Exception as error:
                errors.append(f"{item.get('title')}: {str(error)[:120]}")
        if page >= int(data.get('total_pages') or 1):
            break
    return {'checked': seen, 'added': len(added), 'titles': added, 'errors': errors}


def discover_list(kind='digital', query='', page=1):
    page = max(1, min(int(page or 1), 20))
    if query:
        data = tmdb('/search/movie', {'query': query, 'page': page, 'include_adult': 'false'})
    elif kind == 'digital':
        data = tmdb('/discover/movie', discover_params(page))
    elif kind == 'trending':
        data = tmdb('/trending/movie/week', {'page': page})
    elif kind in {'popular', 'now_playing', 'upcoming', 'top_rated'}:
        data = tmdb(f'/movie/{kind}', {'page': page, 'region': setting('discovery_region') or 'US'})
    else:
        raise ValueError('Unknown list')
    with cx() as c:
        status = {r['tmdb_id']: r['status'] for r in c.execute('SELECT tmdb_id,status FROM movies WHERE tmdb_id IS NOT NULL').fetchall()}
        owned = {(norm(r['title']), r['year']) for r in c.execute("SELECT title,year FROM movies WHERE status='Downloaded'").fetchall()}
    out = []
    for item in data.get('results', []):
        year = _year(item.get('release_date'))
        state = status.get(item['id']) or ('Downloaded' if (norm(item.get('title')), year) in owned else None)
        out.append({'tmdb_id': item['id'], 'title': item.get('title'), 'year': year, 'overview': item.get('overview'),
                    'poster_path': item.get('poster_path'), 'rating': item.get('vote_average'), 'votes': item.get('vote_count'),
                    'release_date': item.get('release_date'), 'status': state})
    return {'results': out, 'page': page, 'total_pages': min(int(data.get('total_pages') or 1), 20)}


# ---------------------------------------------------------------- scheduled work

def _require_library_scan():
    # Never discover or search before the library is known, or owned movies would be downloaded again.
    if not setting('library_scanned_at'):
        scan_library()


def eligible_for_search(limit):
    with cx() as c:
        wanted = [dict(r) for r in c.execute("""SELECT * FROM movies WHERE status='Wanted' AND monitored=1
                                                ORDER BY last_search IS NOT NULL, last_search, added_at DESC""").fetchall()]
        upgrades = [dict(r) for r in c.execute("""SELECT * FROM movies WHERE status='Downloaded' AND monitored=1 AND added_via NOT IN ('plex','library')
                                                  AND COALESCE(resolution,0)>0 AND resolution<? ORDER BY last_search IS NOT NULL, last_search""",
                                               (int(number('cutoff_resolution', 1080)),)).fetchall()]
    out = []
    for movie in wanted:
        if not is_available(movie):
            continue
        wait = 6 if _age_hours(movie.get('added_at')) < 24 * 14 else 24
        if movie.get('last_search') and _age_hours(movie['last_search']) < wait:
            continue
        out.append(movie)
        if len(out) >= limit:
            return out
    for movie in upgrades:
        if movie.get('last_search') and _age_hours(movie['last_search']) < 24 * 7:
            continue
        out.append(movie)
        if len(out) >= limit:
            break
    return out


def run_search():
    if not library_root():
        return {'skipped': 'No movie library folder is set or detected; open Movies > Settings', 'searched': 0}
    _require_library_scan()
    with cx() as c:
        busy = {r['movie_id'] for r in c.execute("SELECT movie_id FROM movie_downloads WHERE status IN ('Queued','Downloading','Downloaded')")}
    auto = flag('auto_grab') and engine.as_bool(engine.get_setting('TVManager', 'auto_grab', '1'), True)
    searched, grabbed, errors = 0, 0, []
    for movie in eligible_for_search(int(number('max_searches_per_run', 10))):
        if movie['id'] in busy:
            continue
        try:
            result = search_movie(movie['id'], auto_grab=auto)
            searched += 1
            grabbed += 1 if result.get('grabbed') else 0
            errors.extend(result.get('errors') or [])
        except Exception as error:
            errors.append(f"{movie['title']}: {str(error)[:200]}")
    return {'searched': searched, 'grabbed': grabbed, 'errors': sorted(set(errors))[:20]}


def run_downloads():
    polled = poll_downloads()
    imported = import_completed()
    return {'poll': polled, 'import': {k: v for k, v in imported.items() if k != 'items'},
            'messages': [i.get('message') for i in imported['items'] if not i.get('ok')][:10]}


def run_job(name):
    if not flag('enabled'):
        return {'skipped': 'Movies are turned off'}
    jobs = {'movie_library_scan': scan_library, 'movie_discovery': discover_auto,
            'movie_search': run_search, 'movie_downloads': run_downloads}
    if name not in jobs:
        raise ValueError('Unknown movie job')
    result = jobs[name]()
    # Indexer and client errors are reported as warnings and retried on the
    # next run; they do not mark the scheduler job failed.
    result['warnings'] = result.pop('errors', None) or []
    return result


# ---------------------------------------------------------------- listing / settings for the UI

PUBLIC_SETTINGS = [k for k in DEFAULTS if k not in {'detected_library_root', 'library_scanned_at', 'last_scan_report'}]


def settings_public():
    data = {k: setting(k) for k in PUBLIC_SETTINGS}
    data['detected_library_root'] = setting('detected_library_root')
    data['library_scanned_at'] = setting('library_scanned_at')
    data['last_scan_report'] = last_scan_report()
    data['effective_library_root'] = library_root()
    folders = plex_movie_folders()
    data['plex_movie_folders'] = folders
    data['library_plex_status'] = library_plex_status(data['effective_library_root'], folders)
    data['destination_list'] = destination_folders()
    data['destination_status'] = destination_status()
    servers = []
    try:
        import advanced
        report = last_scan_report()
        for srv in advanced.media_servers():
            if str(srv.get('kind') or '').lower() != 'plex':
                continue
            seen = [loc for x in report.get('sources', []) if x.get('kind') == 'plex' and x.get('server') == srv.get('name')
                    for loc in x.get('locations') or []]
            servers.append({'id': srv['id'], 'name': srv.get('name'), 'enabled': bool(srv.get('enabled')), 'movie_folders': seen})
    except Exception:
        pass
    data['plex_servers'] = servers
    nzb, torrent = _clients()
    data['nzb_client'] = nzb
    data['torrent_client'] = torrent
    try:
        data['indexers'] = len(providers())
    except Exception:
        data['indexers'] = 0
    data['automation_enabled'] = engine.as_bool(engine.get_setting('TVManager', 'automation_enabled', '0'))
    data['simulation_mode'] = simulation()
    try:
        import tmdb_client
        data['tmdb_configured'] = bool(tmdb_client.configured(engine.DB).get('configured'))
    except Exception:
        data['tmdb_configured'] = False
    return data


def save_settings(body):
    numeric = {'min_free_gb', 'min_rating', 'min_votes', 'discovery_days', 'max_auto_add_per_run', 'max_searches_per_run', 'min_resolution',
               'max_resolution', 'cutoff_resolution', 'min_size_mb', 'max_size_gb', 'stalled_hours'}
    booleans = {'enabled', 'auto_add', 'auto_grab', 'allow_remux', 'allow_hevc'}
    choices = {'torrent_import_method': {'hardlink', 'copy', 'move'}, 'destination_rule': {'most_free', 'in_order'}}
    clean = {}
    for key, value in (body or {}).items():
        if key not in PUBLIC_SETTINGS:
            continue
        value = '' if value is None else str(value).strip()
        if key in booleans:
            value = '1' if value.lower() in {'1', 'true', 'yes', 'on'} else '0'
        elif key in numeric:
            try:
                if float(value) < 0:
                    raise ValueError
            except ValueError:
                raise ValueError(f'{key.replace("_", " ").capitalize()} must be a positive number') from None
        elif key in choices and value not in choices[key]:
            raise ValueError(f'{key} must be one of {", ".join(sorted(choices[key]))}')
        elif key in {'library_root', 'download_dir'} and value and not os.path.isdir(_map(value)):
            raise ValueError(f'Folder not found from this server: {value}')
        elif key == 'destination_folders':
            folders = _split_folders(value)
            missing = [f for f in folders if not os.path.isdir(_map(f))]
            if missing:
                raise ValueError('Movie destination folder not found from this server: ' + ', '.join(missing[:5]))
            value = '\n'.join(folders)
        elif key == 'extra_library_folders':
            folders = _split_folders(value)
            missing = [f for f in folders if not os.path.isdir(_map(f))]
            if missing:
                raise ValueError('Folder not found from this server: ' + ', '.join(missing[:5]))
            value = '\n'.join(folders)
        if len(value) > 8000:
            raise ValueError(f'{key} is too long')
        clean[key] = value
    for key, value in clean.items():
        engine.set_setting(SECTION, key, value)
    if 'destination_folders' in clean:
        # Keep the older single-folder setting in step for anything still reading it.
        engine.set_setting(SECTION, 'library_root', (clean['destination_folders'].split('\n') or [''])[0])
    return settings_public()


def listing(status='', query='', page=1, page_size=60, sort='added'):
    clauses, params = [], []
    if status == 'Missing':
        clauses.append("status IN ('Wanted','Snatched')")
    elif status:
        clauses.append('status=?')
        params.append(status)
    if query:
        clauses.append('(lower(title) LIKE ? OR CAST(year AS TEXT)=?)')
        params += [f'%{query.lower()}%', query]
    where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
    order = {'title': 'title COLLATE NOCASE, year', 'year': 'year DESC, title COLLATE NOCASE',
             'added': 'added_at DESC, id DESC', 'rating': 'rating DESC'}.get(sort, 'added_at DESC, id DESC')
    page = max(1, int(page or 1))
    page_size = max(10, min(int(page_size or 60), 200))
    with cx() as c:
        total = c.execute(f'SELECT COUNT(*) FROM movies {where}', params).fetchone()[0]
        rows = [dict(r) for r in c.execute(f'SELECT * FROM movies {where} ORDER BY {order} LIMIT ? OFFSET ?',
                                           params + [page_size, (page - 1) * page_size]).fetchall()]
        counts = {r['status']: r['n'] for r in c.execute('SELECT status,COUNT(*) n FROM movies GROUP BY status').fetchall()}
        active = {r['movie_id']: dict(r) for r in c.execute("""SELECT movie_id,client,status,progress,release_name FROM movie_downloads
                                                              WHERE status IN ('Queued','Downloading','Downloaded')""").fetchall()}
    for row in rows:
        row['download'] = active.get(row['id'])
        row['available'] = is_available(row)
    return {'movies': rows, 'total': total, 'page': page, 'page_size': page_size, 'counts': counts}


def downloads(limit=100):
    with cx() as c:
        return [dict(r) for r in c.execute("""SELECT d.*,m.title,m.year FROM movie_downloads d JOIN movies m ON m.id=d.movie_id
                                              ORDER BY d.id DESC LIMIT ?""", (int(limit),)).fetchall()]


def results(movie_id):
    with cx() as c:
        return [dict(r) for r in c.execute("""SELECT * FROM movie_search_results WHERE movie_id=?
                                              ORDER BY rejected_reason IS NOT NULL, score DESC LIMIT 200""", (int(movie_id),)).fetchall()]


def update_movie(movie_id, body):
    movie = get_movie(movie_id)
    with cx() as c:
        if 'monitored' in body:
            c.execute('UPDATE movies SET monitored=? WHERE id=?', (1 if engine.as_bool(body['monitored']) else 0, movie['id']))
        if body.get('status') == 'Ignored':
            c.execute("UPDATE movies SET status='Ignored',monitored=0 WHERE id=?", (movie['id'],))
        elif body.get('status') == 'Wanted' and movie['status'] != 'Downloaded':
            c.execute("UPDATE movies SET status='Wanted',monitored=1,last_search=NULL WHERE id=?", (movie['id'],))
        c.commit()
    return get_movie(movie_id)


def retry_download(download_id):
    with cx() as c:
        row = c.execute('SELECT * FROM movie_downloads WHERE id=?', (int(download_id),)).fetchone()
    if not row:
        raise ValueError('Download not found')
    if row['status'] in {'Queued', 'Downloading', 'Downloaded'}:
        fail_download(row['id'], 'Marked failed by user')
    return {'ok': True}


def summary():
    with cx() as c:
        counts = {r['status']: r['n'] for r in c.execute('SELECT status,COUNT(*) n FROM movies GROUP BY status').fetchall()}
        active = c.execute("SELECT COUNT(*) FROM movie_downloads WHERE status IN ('Queued','Downloading','Downloaded')").fetchone()[0]
        jobs = [dict(r) for r in c.execute("""SELECT name,enabled,interval_minutes,last_run,next_run,last_status,last_message
                                              FROM scheduler_jobs WHERE name LIKE 'movie_%' ORDER BY name""").fetchall()]
    for job in jobs:
        job['last_message'] = (job.get('last_message') or '')[:400]
    return {'counts': counts, 'active_downloads': active, 'jobs': jobs, 'settings': settings_public()}


# ---------------------------------------------------------------- shared views (dashboard, calendar, search, insights)

def _setup_problems(settings=None):
    s = settings or settings_public()
    out = []
    if s.get('enabled') != '1':
        out.append(('Movies automation is off', '/movies'))
    if not s.get('effective_library_root'):
        out.append(('No movie destination folder yet', '/movies#settings'))
    elif s.get('destination_status') and not any(d['reachable'] for d in s['destination_status']):
        out.append(('No movie destination folder can be reached', '/movies#settings'))
    if not s.get('tmdb_configured'):
        out.append(('TMDb is not configured', '/metadata-sources'))
    if not s.get('indexers'):
        out.append(('No indexers with a matching download client', '/settings'))
    report = last_scan_report()
    if report and not report.get('complete', True):
        out.append(('A Plex movie library could not be read', '/movies'))
    return out


def dashboard_summary():
    today = date.today()
    week_ago = (datetime.now() - timedelta(days=7)).replace(microsecond=0).isoformat()
    with cx() as c:
        counts = {r['status']: r['n'] for r in c.execute('SELECT status,COUNT(*) n FROM movies GROUP BY status').fetchall()}
        wanted = [dict(r) for r in c.execute("SELECT * FROM movies WHERE status='Wanted' AND monitored=1").fetchall()]
        active = [dict(r) for r in c.execute("""SELECT d.id,d.movie_id,d.client,d.status,d.progress,d.release_name,d.created_at,m.title,m.year,m.poster_path
                                                FROM movie_downloads d JOIN movies m ON m.id=d.movie_id
                                                WHERE d.status IN ('Queued','Downloading','Downloaded') ORDER BY d.id DESC""").fetchall()]
        recent = [dict(r) for r in c.execute("""SELECT id,title,year,poster_path,quality,resolution,downloaded_at,added_via FROM movies
                                                WHERE status='Downloaded' AND downloaded_at IS NOT NULL AND added_via NOT IN ('plex','library')
                                                ORDER BY downloaded_at DESC LIMIT 12""").fetchall()]
        added_week = c.execute("SELECT COUNT(*) FROM movies WHERE added_via IN ('auto','manual') AND added_at>=?", (week_ago.replace('T', ' '),)).fetchone()[0]
        imported_week = c.execute("SELECT COUNT(*) FROM movie_downloads WHERE status='Completed' AND updated_at>=?", (week_ago,)).fetchone()[0]
        failed_week = c.execute("SELECT COUNT(*) FROM movie_downloads WHERE status='Failed' AND updated_at>=?", (week_ago,)).fetchone()[0]
    available = [m for m in wanted if is_available(m)]
    upcoming_movies = sorted((m for m in wanted if not is_available(m) and m.get('available_date')), key=lambda m: m['available_date'])
    settings = settings_public()
    problems = _setup_problems(settings)
    return {
        'counts': {'owned': counts.get('Downloaded', 0), 'wanted': len(available), 'waiting': len(wanted) - len(available),
                   'downloading': len(active), 'ignored': counts.get('Ignored', 0), 'added_week': added_week,
                   'imported_week': imported_week, 'failed_week': failed_week},
        'active': active[:8], 'recent': recent, 'next_release': upcoming_movies[0] if upcoming_movies else None,
        'problems': [{'title': t, 'href': h} for t, h in problems],
        'running': not problems and settings.get('automation_enabled') and not settings.get('simulation_mode'),
        'automation_enabled': settings.get('automation_enabled'), 'today': today.isoformat()}


def recent_downloads(limit=20):
    with cx() as c:
        return [dict(r) for r in c.execute("""SELECT d.id,d.movie_id,d.client,d.status,d.release_name,d.created_at,d.updated_at,m.title,m.year
                                              FROM movie_downloads d JOIN movies m ON m.id=d.movie_id ORDER BY d.id DESC LIMIT ?""",
                                           (int(limit),)).fetchall()]


def calendar(start, end):
    """Wanted movies whose digital or disc release falls in [start, end] (ISO dates)."""
    with cx() as c:
        rows = [dict(r) for r in c.execute("""SELECT id,title,year,poster_path,available_date,release_date,status FROM movies
                                              WHERE status IN ('Wanted','Snatched','Downloaded') AND monitored=1
                                              AND available_date BETWEEN ? AND ? ORDER BY available_date,title""",
                                           (str(start)[:10], str(end)[:10])).fetchall()]
    return rows


def command_search(q, limit=6):
    q = (q or '').strip()
    if not q:
        return []
    with cx() as c:
        rows = c.execute("""SELECT id,title,year,status FROM movies WHERE lower(title) LIKE ? OR imdb_id=? OR CAST(tmdb_id AS TEXT)=?
                            ORDER BY CASE status WHEN 'Downloaded' THEN 1 ELSE 0 END, year DESC LIMIT ?""",
                         (f'%{q.lower()}%', q, q, int(limit))).fetchall()
    label = {'Wanted': 'Wanted movie', 'Snatched': 'Movie downloading', 'Downloaded': 'Movie in library', 'Ignored': 'Ignored movie'}
    return [{'type': 'movie', 'id': r['id'], 'title': f"{r['title']} ({r['year']})" if r['year'] else r['title'],
             'subtitle': label.get(r['status'], 'Movie'), 'href': f"/movie/{r['id']}"} for r in rows]


def insights():
    try:
        d = dashboard_summary()
    except Exception:
        return []
    out = []
    for problem in d['problems'][:2]:
        out.append({'severity': 'warn', 'title': f"Movies: {problem['title']}", 'detail': 'Movie automation needs this before it can run by itself.',
                    'href': problem['href']})
    c = d['counts']
    if c['failed_week']:
        out.append({'severity': 'warn', 'title': f"{c['failed_week']} movie download{'s' if c['failed_week'] != 1 else ''} failed this week",
                    'detail': 'Failed releases were blocklisted and other releases are being searched.', 'href': '/movies#downloads'})
    if c['wanted']:
        out.append({'severity': 'info', 'title': f"{c['wanted']} movie{'s' if c['wanted'] != 1 else ''} wanted",
                    'detail': 'Released movies waiting for a good release on your indexers.', 'href': '/movies'})
    if c['imported_week']:
        out.append({'severity': 'good', 'title': f"{c['imported_week']} movie{'s' if c['imported_week'] != 1 else ''} added to Plex this week",
                    'detail': 'Downloaded, renamed and scanned automatically.', 'href': '/movies'})
    return out


def detail(movie_id):
    movie = get_movie(movie_id)
    with cx() as c:
        history = [dict(r) for r in c.execute('SELECT * FROM movie_downloads WHERE movie_id=? ORDER BY id DESC LIMIT 50', (movie['id'],)).fetchall()]
        try:
            events = [dict(r) for r in c.execute("""SELECT event_type event,message,level,created_at FROM activity_log
                                                    WHERE event_type LIKE 'movie_%' AND (data LIKE ? OR data LIKE ?) ORDER BY id DESC LIMIT 30""",
                                                 (f'%"movie_id": {movie["id"]},%', f'%"movie_id": {movie["id"]}}}%')).fetchall()]
        except Exception:
            events = []
    movie['available'] = is_available(movie)
    return {'movie': movie, 'results': results(movie['id']), 'downloads': history, 'events': events}


# ---------------------------------------------------------------- moving imported movies into the library folder

_relocating = threading.Lock()


def relocation_plan():
    """Movies this app imported whose files are outside the current movie library folder."""
    folders = [f for f in destination_folders() if os.path.isdir(_map(f))]
    if not folders:
        return {'root': '', 'items': [], 'skipped': [], 'message': 'Set a movie destination folder first.'}
    root = folders[0]
    with cx() as c:
        rows = [dict(r) for r in c.execute("""SELECT id,title,year,file_path FROM movies WHERE status='Downloaded'
                                              AND added_via IN ('auto','manual') AND file_path IS NOT NULL ORDER BY title""").fetchall()]
    items, skipped = [], []
    for m in rows:
        current = Path(_map(m['file_path']))
        if any(_inside(current, _map(f)) for f in folders):
            continue
        if not current.exists():
            skipped.append({'id': m['id'], 'title': m['title'], 'reason': f'File not found: {m["file_path"]}'})
            continue
        source = current.parent if current.parent.name == movie_folder_name(m) else current
        try:
            size = sum(p.stat().st_size for p in source.rglob('*') if p.is_file()) if source.is_dir() else source.stat().st_size
        except OSError:
            size = 0
        dest, why = destination_for({}, size)
        if not dest:
            skipped.append({'id': m['id'], 'title': m['title'], 'reason': why})
            continue
        target = Path(_map(dest)) / movie_folder_name(m)
        if source.is_file():
            target = target / current.name
        if target.exists():
            skipped.append({'id': m['id'], 'title': m['title'], 'reason': f'Already exists in the library folder: {target}'})
            continue
        items.append({'id': m['id'], 'title': m['title'], 'year': m['year'], 'from': str(source), 'to': str(target), 'dest': dest,
                      'file': str(target / current.name) if source != current else str(target)})
    return {'root': root, 'folders': folders, 'items': items, 'skipped': skipped}


def relocate_imported(background=True):
    plan = relocation_plan()
    if not plan['items']:
        return dict(plan, started=False)
    if not _relocating.acquire(blocking=False):
        raise ValueError('Movies are already being moved; wait for that to finish.')

    def work():
        moved, failed = 0, []
        try:
            for item in plan['items']:
                try:
                    Path(item['to']).parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(item['from'], item['to'])
                    with cx() as c:
                        c.execute('UPDATE movies SET file_path=? WHERE id=?', (item['file'], item['id']))
                        c.commit()
                    moved += 1
                    log('movie_moved', f"Moved {item['title']} ({item.get('year') or '?'}) to {item['to']}", data={'movie_id': item['id']})
                except Exception as error:
                    failed.append(item['title'])
                    log('movie_move_error', f"Could not move {item['title']}: {str(error)[:200]}", 'warning', data={'movie_id': item['id']})
            done = []
            for item in plan['items']:
                if Path(item['to']).exists() and item['to'] not in done:
                    done.append(item['to'])
            for folder in done:
                refresh_media_servers(folder)
            log('movie_relocation', f"Moved {moved} movie(s) into the movie destination folders" + (f"; {len(failed)} could not be moved" if failed else ''),
                'warning' if failed else 'info')
        finally:
            _relocating.release()
    if background:
        threading.Thread(target=work, daemon=True, name='TVManagerMovieRelocation').start()
    else:
        work()
    return dict(plan, started=True)
