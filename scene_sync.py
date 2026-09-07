"""Cached XEM mappings kept separate from operator numbering overrides."""
from pathlib import Path
import time
import requests
import dbcore

DB=Path(__file__).resolve().parent/'tvmanager.db'

def init():
    with dbcore.connect(DB) as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS xem_mappings(
          show_id INTEGER,season INTEGER,episode INTEGER,scene_season INTEGER,scene_episode INTEGER,
          absolute_number INTEGER,scene_absolute_number INTEGER,
          PRIMARY KEY(show_id,season,episode,scene_season,scene_episode));
          CREATE TABLE IF NOT EXISTS xem_refresh(show_id INTEGER PRIMARY KEY,checked_at REAL,status TEXT);''')

def parse(payload):
    if payload.get('result')!='success' or not isinstance(payload.get('data'),list):raise ValueError('XEM did not return a successful mapping response')
    result=[]
    for item in payload['data']:
        origin=item.get('tvdb')
        if not isinstance(origin,dict):continue
        for key in ('scene','scene_2'):
            dest=item.get(key)
            if not isinstance(dest,dict):continue
            try:
                nums=[int(origin['season']),int(origin['episode']),int(dest['season']),int(dest['episode'])]
                if any(n<0 for n in nums):raise ValueError()
                absolute=int(origin.get('absolute') or 0) or None
                scene_absolute=int(dest.get('absolute') or 0) or None
                result.append((*nums,absolute,scene_absolute))
            except (KeyError,ValueError,TypeError):raise ValueError('XEM returned invalid episode numbering')
    return list(dict.fromkeys(result))

def refresh(show_id,force=False):
    with dbcore.connect(DB,readonly=True) as c:
        show=c.execute('SELECT tvdb_id FROM shows WHERE id=?',(show_id,)).fetchone()
        previous=c.execute('SELECT checked_at,status FROM xem_refresh WHERE show_id=?',(show_id,)).fetchone()
    if not show or not show['tvdb_id']:raise ValueError('A TVDB show ID is required for scene mapping')
    if not force and previous and time.time()-previous['checked_at']<86400:return {'cached':True,'message':previous['status']}
    try:
        response=requests.get('https://thexem.info/map/all',params={'id':int(show['tvdb_id']),'origin':'tvdb','destination':'scene'},timeout=15)
        response.raise_for_status();rows=parse(response.json())
    except (requests.RequestException,ValueError) as exc:
        # Preserve the last good mappings if the external service fails.
        raise ValueError('Scene mapping could not be refreshed; previous mappings were preserved') from exc
    with dbcore.connect(DB) as c:
        current=c.execute('SELECT tvdb_id FROM shows WHERE id=?',(show_id,)).fetchone()
        if not current or current['tvdb_id']!=show['tvdb_id']:raise ValueError('Show identity changed during refresh')
        c.execute('DELETE FROM xem_mappings WHERE show_id=?',(show_id,))
        c.executemany('INSERT INTO xem_mappings VALUES(?,?,?,?,?,?,?)',[(show_id,*row) for row in rows])
        message=f'{len(rows)} scene mappings available'
        c.execute('INSERT INTO xem_refresh VALUES(?,?,?) ON CONFLICT(show_id) DO UPDATE SET checked_at=excluded.checked_at,status=excluded.status',(show_id,time.time(),message))
    return {'cached':False,'mappings':len(rows),'message':message}

def for_search(show_id,episode):
    result=dict(episode)
    # Existing per-episode values are explicit/imported overrides.
    if result.get('scene_season') is not None and result.get('scene_episode') is not None:return result
    with dbcore.connect(DB,readonly=True) as c:
        row=c.execute('SELECT * FROM xem_mappings WHERE show_id=? AND season=? AND episode=? ORDER BY scene_season,scene_episode LIMIT 1',(show_id,result['season'],result['episode'])).fetchone()
    if row:
        result['scene_season']=row['scene_season'];result['scene_episode']=row['scene_episode']
        result['absolute_number']=row['scene_absolute_number'] or row['absolute_number'] or result.get('absolute_number')
    return result

def episode_rows(c,show_id,season,episode):
    manual=c.execute('SELECT * FROM episodes WHERE show_id=? AND scene_season=? AND scene_episode=?',(show_id,season,episode)).fetchall()
    if manual:return manual
    rows=c.execute('''SELECT e.* FROM episodes e JOIN xem_mappings x ON x.show_id=e.show_id AND x.season=e.season AND x.episode=e.episode
                      WHERE x.show_id=? AND x.scene_season=? AND x.scene_episode=?
                      AND (e.scene_season IS NULL OR e.scene_episode IS NULL) ORDER BY e.season,e.episode''',(show_id,season,episode)).fetchall()
    return rows or c.execute('SELECT * FROM episodes WHERE show_id=? AND season=? AND episode=?',(show_id,season,episode)).fetchall()
