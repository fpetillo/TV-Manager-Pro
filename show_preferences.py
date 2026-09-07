"""Validated per-show behavior shared by search, metadata and subtitles."""
import re

COLUMNS={'metadata_language':"TEXT DEFAULT 'en-US'",'past_episode_status':"TEXT DEFAULT 'Wanted'",'future_episode_status':"TEXT DEFAULT 'Wanted'",'subtitles_enabled':'INTEGER DEFAULT 1'}
BOOLS={'paused','monitor_new','search_enabled','season_folders','scene_numbering','air_by_date','sports','metadata_enabled','favorite','anime','subtitles_enabled'}
IDS={'quality_profile_id','retention_policy_id'}
TEXT={'preferred_words','required_words','ignored_words','metadata_language','past_episode_status','future_episode_status'}


def init(c):
    existing={r[1] for r in c.execute('PRAGMA table_info(shows)')}
    for name,definition in COLUMNS.items():
        if name not in existing:c.execute(f'ALTER TABLE shows ADD COLUMN {name} {definition}')


def options(body):
    result={}
    for key,value in body.items():
        if key in BOOLS:
            if value not in (True,False,0,1,'0','1','true','false'):raise ValueError(f'Invalid switch: {key}')
            result[key]=int(value in (True,1,'1','true'))
        elif key in IDS:
            if value in ('',None):result[key]=None
            elif str(value).isdigit() and int(value)>0:result[key]=int(value)
            else:raise ValueError(f'Invalid selection: {key}')
        elif key in TEXT:
            value=str(value or '').strip()
            if key=='metadata_language' and not re.fullmatch(r'[a-z]{2,3}(?:-[A-Z]{2})?',value):raise ValueError('Use a metadata language such as en-US or fr-FR.')
            if key.endswith('_episode_status') and value not in {'Wanted','Skipped','Ignored'}:raise ValueError('Default episode status must be Wanted, Skipped or Ignored.')
            result[key]=value
    return result


def initial_episode_status(show,airdate,today):
    key='future_episode_status' if airdate and airdate>today else 'past_episode_status'
    value=dict(show).get(key) or 'Wanted'
    return 'Unaired' if key=='future_episode_status' and value=='Wanted' else value


def search_parameters(show,episode):
    show,episode=dict(show),dict(episode)
    name=show.get('search_name') or show['name']
    if (show.get('air_by_date') or show.get('sports')) and episode.get('airdate'):
        air=str(episode['airdate'])[:10]
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}',air):return {'t':'search','q':name+' '+air.replace('-','.')}
    if show.get('anime') and episode.get('absolute_number') is not None:
        return {'t':'search','q':name+' '+str(episode['absolute_number']).zfill(3)}
    season,number=episode['season'],episode['episode']
    if show.get('scene_numbering') and episode.get('scene_season') is not None and episode.get('scene_episode') is not None:
        season,number=episode['scene_season'],episode['scene_episode']
    return {'t':'tvsearch','q':name,'season':season,'ep':number}


def apply(c,sid,body):
    values=options(body)
    for field,table in (('quality_profile_id','quality_profiles'),('retention_policy_id','retention_policies')):
        if values.get(field) and not c.execute(f'SELECT id FROM {table} WHERE id=?',(values[field],)).fetchone():raise ValueError('Selected profile no longer exists')
    if values:c.execute('UPDATE shows SET '+','.join(k+'=?' for k in values)+' WHERE id=?',[*values.values(),sid])
