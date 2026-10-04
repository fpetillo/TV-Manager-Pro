import json
import pytest
import dbcore
import engine
import production
import indexer_client
import search_names
import show_preferences

TITLE="Wonka's The Golden Ticket"


def item(title,guid='fixture'):
    return dict(title=title,guid=guid,url='https://fixture.test/'+guid,size=100,seeders=10,publish_date=None)


@pytest.mark.parametrize('title,expected',[
    (TITLE,'Wonkas The Golden Ticket'),('Wonka’s The Golden Ticket','Wonka s The Golden Ticket'),
    ('Spider-Man','Spider Man'),('Spider-Man','SpiderMan'),('S.W.A.T.','SWAT'),
    ('Law & Order','Law and Order'),('Café Society','Cafe Society'),('Blue—Moon','Blue Moon'),
    ('Pokémon: Horizons','Pokemon Horizons'),('東京ドラマ','東京ドラマ')])
def test_query_variants_preserve_text_and_are_bounded(title,expected):
    names=search_names.variants(title)
    assert names[0]==title and expected in names and len(names)<=6
    assert len({x.casefold() for x in names})==len(names)
    assert search_names.variants('Friends')==['Friends']
    assert search_names.variants('!@#')==[]


@pytest.fixture
def store(tmp_path,monkeypatch):
    database=tmp_path/'search.db'
    for module in [engine,production]:monkeypatch.setattr(module,'DB',database)
    with dbcore.connect(database) as c:
        c.executescript('''
        CREATE TABLE shows(id INTEGER PRIMARY KEY,name,paused,search_enabled,preferred_words,required_words,ignored_words,quality,quality_profile_id,scene_numbering,air_by_date,sports,anime);
        CREATE TABLE episodes(id INTEGER PRIMARY KEY,show_id,season,episode,status,monitored,ignored,last_search,search_count,airdate);
        CREATE TABLE search_results(id INTEGER PRIMARY KEY,episode_id,provider,protocol,title,url,guid,size,publish_date,seeders,quality,score,rejected_reason,status,raw_json);
        CREATE TABLE season_pack_searches(id INTEGER PRIMARY KEY,show_id,season,provider,title,url,guid,size,seeders,quality,score);
        INSERT INTO episodes VALUES(1,1,1,2,'Wanted',1,0,NULL,0,'2026-10-02');
        ''')
        c.execute("INSERT INTO shows VALUES(1,?,0,1,'','','','HD',NULL,0,0,0,0)",(TITLE,))
        show_preferences.init(c)
        c.execute("UPDATE shows SET preferred_resolution='1080p'")
    monkeypatch.setattr(engine,'ignore_specials_from_wanted',lambda:False)
    monkeypatch.setattr(engine,'get_setting',lambda section,name,default=None:default)
    monkeypatch.setattr(engine.advanced,'aliases',lambda *a:[])
    monkeypatch.setattr(engine.advanced,'provider_defs_raw',lambda:[])
    monkeypatch.setattr(engine,'parse_newznab',lambda:[{'name':'Fixture','enabled':True,'protocol':'newznab'}])
    monkeypatch.setattr(engine.ops,'provider_is_available',lambda *a:True)
    monkeypatch.setattr(engine.ops,'provider_result',lambda *a,**k:None)
    monkeypatch.setattr(engine.ops,'apply_rules',lambda result:result)
    monkeypatch.setattr(engine.ops,'record_decision',lambda *a,**k:None)
    monkeypatch.setattr(engine,'log',lambda *a,**k:None)
    return database


@pytest.mark.parametrize('auto_grab',[False,True])
def test_real_episode_search_falls_back_without_renaming_and_stops_on_success(store,monkeypatch,auto_grab):
    calls=[]
    def search(p,params,timeout):
        calls.append(params)
        return [item('Wonkas.The.Golden.Ticket.S01E02.1080p.WEB')]*2 if params['q']=='Wonkas The Golden Ticket' else []
    monkeypatch.setattr(indexer_client,'search',search)
    grabs=[]
    monkeypatch.setattr(engine,'grab_result',lambda rid:grabs.append(rid) or {'ok':True})
    result=engine.search_episode(1,auto_grab=auto_grab)
    assert len(grabs)==int(auto_grab)
    assert [p['q'] for p in calls]==[TITLE,'Wonkas The Golden Ticket']
    assert all(p['season']==1 and p['ep']==2 for p in calls)
    assert len(result['results'])==1 and result['results'][0]['rejected_reason'] is None
    assert result['results'][0]['search_name']=='Wonkas The Golden Ticket'
    with dbcore.connect(store) as c:
        assert c.execute('SELECT name,name_override FROM shows').fetchone()[:]==(TITLE,None)
        assert c.execute('SELECT season,episode FROM episodes').fetchone()[:]==(1,2)
        assert json.loads(c.execute('SELECT raw_json FROM search_results').fetchone()[0])['search_name']=='Wonkas The Golden Ticket'


def test_original_success_does_not_spend_requests_on_variants(store,monkeypatch):
    calls=[]
    monkeypatch.setattr(indexer_client,'search',lambda p,q,t:calls.append(q) or [item(TITLE+'.S01E02.1080p.WEB')])
    assert len(engine.search_episode(1)['results'])==1 and len(calls)==1


@pytest.mark.parametrize('release',['Unrelated.Show.S01E02.1080p','Wonkas.The.Golden.Ticket.S01E03.1080p','Wonkas.The.Golden.Ticket.US.S01E02.1080p','Wonkas.The.Golden.Ticket.2025.S01E02.1080p'])
def test_broader_query_cannot_auto_grab_wrong_show_or_episode_even_with_accept_rule(store,monkeypatch,release):
    monkeypatch.setattr(indexer_client,'search',lambda p,q,t:[] if q['q']==TITLE else [item(release)])
    monkeypatch.setattr(engine.ops,'apply_rules',lambda row:dict(row,rejected_reason=None))
    monkeypatch.setattr(engine,'grab_result',lambda *a:pytest.fail('Unrelated broad result must not download'))
    result=engine.search_episode(1,auto_grab=True)
    assert result['results'][0]['rejected_reason'] and result['grabbed'] is None


@pytest.mark.parametrize('name,show,episode,title',[
    (TITLE,{},dict(season=1,episode=2),'Wonka.s.The.Golden.Ticket.1x02.1080p'),
    ('Café Talk',{'air_by_date':1},dict(season=1,episode=2,airdate='2026-10-02'),'Cafe.Talk.2026.10.02.1080p'),
    ('Café Anime',{'anime':1},dict(season=1,episode=2,absolute_number=52),'[Group] Cafe Anime - 052v2 [1080p]'),
    ('Spider-Man',{'scene_numbering':1},dict(season=1,episode=2,scene_season=3,scene_episode=4),'SpiderMan.S03E04.1080p'),
])
def test_broad_match_respects_date_absolute_and_scene_numbering(name,show,episode,title):
    assert search_names.release_rejection(title,name,show,episode) is None
    assert search_names.release_rejection('Different.'+title,name,show,episode)


def test_rate_limit_stops_fallbacks_and_preserves_earlier_results(store,monkeypatch):
    calls=[]
    def search(p,q,t):
        calls.append(q['q'])
        if q['q']==TITLE:return [item('Wonkas.The.Golden.Ticket.S01E02.720p.WEB')]
        raise indexer_client.IndexerError('Rate limit',retry_after=600)
    monkeypatch.setattr(indexer_client,'search',search)
    result=engine.search_episode(1)
    assert len(calls)==2 and len(result['results'])==1 and result['errors']
    assert '1080p' in result['results'][0]['rejected_reason']


def test_pack_search_uses_aliases_variants_numbering_and_deduplicates(store,monkeypatch):
    monkeypatch.setattr(engine.advanced,'aliases',lambda sid:['Wonkas The Golden Ticket'])
    monkeypatch.setattr(engine.advanced,'provider_defs_raw',lambda:[{'name':'Disabled','enabled':False}])
    calls=[]
    def search(p,q):
        assert p['name']=='Fixture';calls.append(q['q'])
        if q['q']==TITLE:return []
        return [item('Wonkas.The.Golden.Ticket.S01.1080p')]*2+[item('Other.Show.S01.1080p','other'),item('Wonkas.The.Golden.Ticket.S02.1080p','wrong'),item('Wonkas.The.Golden.Ticket.S01E02.1080p','episode')]
    monkeypatch.setattr(indexer_client,'search',search)
    result=production.season_pack_search(1,1)
    assert len(result['results'])==1 and result['results'][0]['search_name']=='Wonkas The Golden Ticket'
    assert calls==[TITLE,'Wonkas The Golden Ticket'] and not result['errors']


def test_http_text_fallback_keeps_episode_suffix_and_capability_cache(store,monkeypatch):
    indexer_client._caps.clear();calls=[]
    class Response:
        status_code=200;headers={}
        def __init__(self,data):self.data=data
        def iter_content(self,n):yield self.data
        def close(self):pass
    def get(url,**kwargs):
        p=kwargs['params'];calls.append(dict(p))
        if p['t']=='caps':return Response(b'<caps><searching><search available="yes" supportedParams="q"/></searching></caps>')
        assert p['t']=='search' and p['q'].endswith(' S01E02')
        items='<item><title>Wonkas.The.Golden.Ticket.S01E02.1080p</title><guid>one</guid><link>https://fixture.test/file</link></item>' if p['q'].startswith('Wonkas ') else ''
        return Response(('<rss><channel>'+items+'</channel></rss>').encode())
    monkeypatch.setattr(indexer_client.requests,'get',get)
    result=engine.search_generic_provider({'name':'Fixture','url':'https://fixture.test'}, {'name':TITLE,'preferred_resolution':'1080p'}, {'season':1,'episode':2})
    assert len(result)==1 and not result[0]['rejected_reason']
    assert [p['t'] for p in calls]==['caps','search','search']
