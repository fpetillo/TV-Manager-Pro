import sqlite3
from pathlib import Path
from types import SimpleNamespace
from contextlib import closing
import base64
import engine, show_preferences, advanced, dbcore


def test_quality_profile_ids_are_not_booleanized():
    assert show_preferences.options({'quality_profile_id':4,'paused':'false'})=={'quality_profile_id':4,'paused':0}


def test_future_status_and_existing_status_contract():
    assert show_preferences.initial_episode_status({'future_episode_status':'Skipped'},'2030-01-01','2026-09-07')=='Skipped'
    assert show_preferences.initial_episode_status({},'2030-01-01','2026-09-07')=='Unaired'
    assert show_preferences.initial_episode_status({'past_episode_status':'Ignored'},'2020-01-01','2026-09-07')=='Ignored'


def test_scene_date_and_absolute_search_queries():
    episode={'season':1,'episode':2,'scene_season':3,'scene_episode':4,'absolute_number':52,'airdate':'2026-09-07'}
    assert show_preferences.search_parameters({'name':'Show','scene_numbering':1},episode)['season']==3
    assert show_preferences.search_parameters({'name':'Show','anime':1},episode)=={'t':'search','q':'Show 052'}
    assert show_preferences.search_parameters({'name':'Show','sports':1},episode)=={'t':'search','q':'Show 2026.09.07'}


def test_provider_receives_date_query_without_season(monkeypatch):
    seen={}
    def get(url,**kwargs):
        seen.update(kwargs['params'])
        return SimpleNamespace(content=b'<rss><channel/></rss>',raise_for_status=lambda:None)
    monkeypatch.setattr(engine.requests,'get',get)
    engine.search_generic_provider({'url':'https://example.test','name':'test'},{'name':'Show','air_by_date':1},{'season':1,'episode':2,'airdate':'2026-09-07'})
    assert seen['q']=='Show 2026.09.07' and 'season' not in seen and 'ep' not in seen


def test_magnet_hash_supports_hex_base32_and_rejects_invalid():
    value='0123456789abcdef0123456789abcdef01234567'
    encoded=base64.b32encode(bytes.fromhex(value)).decode()
    assert engine._magnet_hash('magnet:?xt=urn:btih:'+encoded)==value
    assert engine._magnet_hash('https://example.test/?xt=urn:btih:'+value) is None
    assert engine._magnet_hash('magnet:?xt=urn:btih:garbage') is None


def test_episode_context_is_mapping_and_aired_unaired_is_searchable(tmp_path,monkeypatch):
    database=tmp_path/'test.db';monkeypatch.setattr(engine,'DB',database)
    with dbcore.connect(database) as c:
        c.executescript('''CREATE TABLE shows(id INTEGER PRIMARY KEY,name,paused,search_enabled,preferred_words,required_words,ignored_words,quality,quality_profile_id,scene_numbering,air_by_date,sports,anime);
        CREATE TABLE episodes(id INTEGER PRIMARY KEY,show_id,season,episode,status,monitored,ignored,airdate);
        CREATE TABLE settings(section,name,value);
        INSERT INTO shows VALUES(1,'Show',0,1,'','','','HD',4,0,0,0,0);
        INSERT INTO episodes VALUES(1,1,1,1,'Unaired',1,0,'2020-01-01');
        INSERT INTO episodes VALUES(2,1,1,2,'Unaired',1,0,'2099-01-01');''')
    assert engine._episode_context(1).get('quality_profile_id')==4
    assert engine.eligible_episodes('backlog',10)==[1]


def test_scene_exceptions_are_used_as_search_aliases(tmp_path,monkeypatch):
    monkeypatch.setattr(advanced,'DB',tmp_path/'aliases.db')
    with advanced.cx() as c:
        c.executescript("CREATE TABLE scene_mappings(show_id,alias);CREATE TABLE scene_exceptions(id,show_id,exception_name);INSERT INTO scene_exceptions VALUES(1,9,'Alternate Name');")
    assert advanced.aliases(9)==['Alternate Name']


def test_flat_folder_setting_applies_when_renaming():
    import naming
    path=naming.configured_destination('/tv/Show','Show',[{'season':1,'episode':2,'name':'Pilot'}],'source.mkv','Season %0S/%SN - S%0SE%0E',True,False)
    assert path==Path('/tv/Show/Show - S01E02.mkv')


def test_episode_search_and_retrieve_with_real_sqlite_rows(tmp_path,monkeypatch):
    database=tmp_path/'search.db';monkeypatch.setattr(engine,'DB',database)
    with dbcore.connect(database) as c:
        c.executescript("""CREATE TABLE shows(id INTEGER PRIMARY KEY,name,paused,search_enabled,preferred_words,required_words,ignored_words,quality,quality_profile_id,scene_numbering,air_by_date,sports,anime);
        CREATE TABLE episodes(id INTEGER PRIMARY KEY,show_id,season,episode,status,monitored,ignored,last_search,search_count);
        CREATE TABLE search_results(id INTEGER PRIMARY KEY,episode_id,provider,protocol,title,url,guid,size,publish_date,seeders,quality,score,rejected_reason,status,raw_json);
        INSERT INTO shows VALUES(1,'Show',0,1,'','','','HD',NULL,0,0,0,0);
        INSERT INTO episodes VALUES(1,1,1,2,'Wanted',1,0,NULL,0);""")
    monkeypatch.setattr(engine,'ignore_specials_from_wanted',lambda:False)
    monkeypatch.setattr(engine,'get_setting',lambda *a:'0')
    monkeypatch.setattr(engine.advanced,'aliases',lambda *a:[])
    monkeypatch.setattr(engine.advanced,'provider_defs_raw',lambda:[])
    monkeypatch.setattr(engine,'parse_newznab',lambda:[{'name':'Fixture','enabled':True}])
    monkeypatch.setattr(engine.ops,'provider_is_available',lambda *a:True)
    monkeypatch.setattr(engine.ops,'provider_result',lambda *a:None)
    monkeypatch.setattr(engine.ops,'apply_rules',lambda result:result)
    monkeypatch.setattr(engine.ops,'record_decision',lambda *a,**k:None)
    monkeypatch.setattr(engine,'log',lambda *a,**k:None)
    def provider(p,show,episode):
        assert show.get('name')=='Show' and episode.get('episode')==2
        return [dict(provider='Fixture',protocol='nzb',title='Show S01E02',url='https://example.test/file',guid='fixture',size=100,publish_date=None,seeders=0,quality='HD',score=10,rejected_reason=None)]
    monkeypatch.setattr(engine,'search_newznab',provider)
    grabs=[]
    monkeypatch.setattr(engine,'grab_result',lambda result_id:grabs.append(result_id) or {'ok':True})
    result=engine.search_episode(1,auto_grab=False)
    assert not result['errors'] and len(result['results'])==1 and not grabs
    result=engine.search_episode(1,auto_grab=True)
    assert result['grabbed']=={'ok':True} and grabs==[result['results'][0]['id']]
    with dbcore.connect(database,readonly=True) as c:
        assert c.execute('SELECT search_count FROM episodes WHERE id=1').fetchone()[0]==2
        assert c.execute("SELECT COUNT(*) FROM search_results WHERE status='Found'").fetchone()[0]==1
