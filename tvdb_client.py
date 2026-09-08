"""TheTVDB v4 client using operator-provided API credentials."""
from pathlib import Path
import threading
import time
import requests
import dbcore

DB=Path(__file__).resolve().parent/'tvmanager.db'
BASE='https://api4.thetvdb.com/v4'
_tokens={}
_lock=threading.Lock()

def credentials(db=None):
    with dbcore.connect(db or DB,readonly=True) as c:
        values={r['name']:r['value'] for r in c.execute("SELECT name,value FROM settings WHERE section='TVDB'")}
    return values.get('api_key',''),values.get('pin','')

def token(db=None,force=False):
    key,pin=credentials(db)
    if not key:raise ValueError('Configure your TVDB API key in Metadata Sources first')
    with _lock:
        cached=_tokens.get((key,pin))
        if cached and not force and time.time()<cached[1]:return cached[0]
        body={'apikey':key}
        if pin:body['pin']=pin
        try:
            r=requests.post(BASE+'/login',json=body,timeout=20);r.raise_for_status();value=(r.json().get('data') or {}).get('token')
        except (requests.RequestException,ValueError) as exc:raise ValueError('TVDB login failed; check your API key and subscriber PIN') from exc
        if not value:raise ValueError('TVDB did not return an access token')
        _tokens.clear();_tokens[(key,pin)]=(value,time.time()+27*86400)
        return value

def get(path,params=None,db=None):
    access=token(db)
    try:
        r=requests.get(BASE+path,params=params or {},headers={'Authorization':'Bearer '+access},timeout=20)
        if r.status_code==401:r=requests.get(BASE+path,params=params or {},headers={'Authorization':'Bearer '+token(db,force=True)},timeout=20)
        r.raise_for_status();data=r.json()
    except (requests.RequestException,ValueError) as exc:raise ValueError('TVDB request failed; check service availability and credentials') from exc
    if data.get('status')!='success':raise ValueError('TVDB did not return a successful response')
    return data

def search(query,year=None,db=None):
    params={'query':query,'type':'series','limit':20}
    if year:params['year']=year
    rows=get('/search',params,db).get('data') or []
    results=[]
    for row in rows:
        tid=row.get('tvdb_id')
        if not str(tid).isdigit():continue
        results.append({'tvdb_id':int(tid),'metadata_provider':'tvdb','name':row.get('name') or row.get('title') or 'Unknown','overview':row.get('overview') or '',
                        'first_air_date':row.get('first_air_time'),'poster':row.get('image_url') or row.get('thumbnail'),'network':row.get('network'),'tmdb_id':None,'imdb_id':None})
    return results

def language_code(language):
    language=str(language or 'en-US').split('-')[0]
    code={'en':'eng','fr':'fra','de':'deu','es':'spa','it':'ita','pt':'por','ja':'jpn','ko':'kor','zh':'zho','nl':'nld','ru':'rus','ar':'ara','pl':'pol','sv':'swe','da':'dan','fi':'fin','no':'nor','tr':'tur','uk':'ukr','he':'heb','cs':'ces','hu':'hun'}.get(language,language if len(language)==3 else None)
    if not code:raise ValueError('Use the TVDB three-letter language code for this metadata language')
    return code

def show_payload(show,db=None):
    tid=show.get('tvdb_id')
    if not tid:raise ValueError('The show has no TVDB ID')
    info=get(f'/series/{int(tid)}/extended',{'meta':'translations','short':'true'},db)['data']
    language=language_code(show.get('metadata_language'))
    name,overview=info.get('name'),info.get('overview') or ''
    translations=info.get('translations') or {}
    for row in translations.get('nameTranslations',[]):
        if row.get('language')==language:name=row.get('name') or name
    for row in translations.get('overviewTranslations',[]):
        if row.get('language')==language:overview=row.get('overview') or overview
    episodes=[];seen=set()
    order=show.get('episode_order') or 'official'
    if order not in {'official','dvd'}:raise ValueError('Unsupported TVDB episode order')
    for page in range(500):
        data=get(f'/series/{int(tid)}/episodes/{order}/{language}',{'page':page},db)
        rows=(data.get('data') or {}).get('episodes') or []
        before=len(seen)
        for row in rows:
            if row.get('id') in seen:continue
            seen.add(row.get('id'));episodes.append(row)
        if not (data.get('links') or {}).get('next'):break
        if not rows or len(seen)==before:raise ValueError('TVDB pagination stopped before the last page')
    else:raise ValueError('TVDB episode pagination exceeded the supported limit')
    seasons={}
    for ep in episodes:
        if ep.get('seasonNumber') is None or ep.get('number') is None:continue
        seasons.setdefault(int(ep['seasonNumber']),{'episodes':[]})['episodes'].append({'id':ep.get('id'),'episode_number':int(ep['number']),'name':ep.get('name'),'overview':ep.get('overview'),'air_date':ep.get('aired'),'image':ep.get('image')})
    normalized={'name':name,'original_name':info.get('name'),'overview':overview,'first_air_date':info.get('firstAired'),'poster':info.get('image'),
                'external_ids':{'tvdb_id':int(tid)},'genres':info.get('genres') or [],'networks':[info.get('originalNetwork')] if info.get('originalNetwork') else [],'seasons':[]}
    return normalized,sorted(seasons.items())

def refresh_show(show,db=None):
    from datetime import date
    import show_preferences
    db=db or DB;info,seasons=show_payload(show,db)
    inserted=updated=0
    with dbcore.connect(db) as c:
        current=c.execute('SELECT tvdb_id,metadata_provider FROM shows WHERE id=?',(show['id'],)).fetchone()
        if not current or current['tvdb_id']!=show['tvdb_id'] or current['metadata_provider']!='tvdb':raise ValueError('Show metadata source changed during refresh')
        c.execute("UPDATE shows SET name=COALESCE(NULLIF(name_override,''),?),overview=?,poster=COALESCE(?,poster),first_air_date=?,network=?,genre=? WHERE id=?",
                  (info['name'],info['overview'],info.get('poster'),info['first_air_date'],', '.join(n.get('name','') for n in info['networks']),', '.join(g.get('name','') for g in info['genres']),show['id']))
        for season,payload in seasons:
            for ep in payload['episodes']:
                existing=c.execute('SELECT id,tvdb_episode_id FROM episodes WHERE show_id=? AND season=? AND episode=?',(show['id'],season,ep['episode_number'])).fetchone()
                if existing:
                    if existing['tvdb_episode_id'] and existing['tvdb_episode_id']!=ep['id']:raise ValueError('TVDB episode identity changed; review numbering before refreshing')
                    c.execute('UPDATE episodes SET name=?,overview=?,airdate=?,still_url=COALESCE(?,still_url),tvdb_episode_id=?,metadata_updated_at=CURRENT_TIMESTAMP WHERE id=?',
                              (ep['name'],ep['overview'],ep['air_date'],ep['image'],ep['id'],existing['id']));updated+=1
                else:
                    status=show_preferences.initial_episode_status(show,ep['air_date'],date.today().isoformat())
                    c.execute('INSERT INTO episodes(show_id,season,episode,name,overview,airdate,still_url,tvdb_episode_id,status,metadata_updated_at) VALUES(?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)',
                              (show['id'],season,ep['episode_number'],ep['name'],ep['overview'],ep['air_date'],ep['image'],ep['id'],status));inserted+=1
        c.execute("INSERT INTO metadata_refresh_state(show_id,last_refresh,last_status,last_error,updated_at) VALUES(?,CURRENT_TIMESTAMP,'OK',NULL,CURRENT_TIMESTAMP) ON CONFLICT(show_id) DO UPDATE SET last_refresh=CURRENT_TIMESTAMP,last_status='OK',last_error=NULL,updated_at=CURRENT_TIMESTAMP",(show['id'],))
    result={'show_id':show['id'],'name':info['name'],'tvdb_id':show['tvdb_id'],'inserted':inserted,'updated':updated,'metadata_provider':'tvdb'}
    if show.get('scene_numbering'):
        try:
            import scene_sync
            result['scene_mapping']=scene_sync.refresh(show['id'])
        except ValueError as exc:result['scene_mapping']={'error':str(exc)}
    return result
