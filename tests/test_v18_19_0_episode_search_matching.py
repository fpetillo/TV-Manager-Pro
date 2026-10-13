import pytest
import dbcore
import engine
import production
import indexer_client
import search_names
import show_preferences

BROTHERS_RESULTS=['Band.of.Brothers.S01E01.1080p.BluRay','Brothers.and.Sisters.S01E01.1080p.WEB',
                  'The.Brothers.Sun.S01E01.1080p.WEB','Brothers.1984.S01E01.1080p','Brothers.S01E01.720p.HDTV',
                  'Brothers.2009.S01E01.1080p.WEB']


def item(title):
    return dict(title=title,guid=title,url='https://fixture.test/'+title,size=100,seeders=10,publish_date=None)


@pytest.fixture
def store(tmp_path,monkeypatch):
    database=tmp_path/'search.db'
    for module in [engine,production]:monkeypatch.setattr(module,'DB',database)
    with dbcore.connect(database) as c:
        c.executescript('''
        CREATE TABLE shows(id INTEGER PRIMARY KEY,name,paused,search_enabled,preferred_words,required_words,ignored_words,quality,quality_profile_id,scene_numbering,air_by_date,sports,anime,first_air_date,tvdb_id,imdb_id,tmdb_id);
        CREATE TABLE episodes(id INTEGER PRIMARY KEY,show_id,season,episode,status,monitored,ignored,last_search,search_count,airdate);
        CREATE TABLE search_results(id INTEGER PRIMARY KEY,episode_id,provider,protocol,title,url,guid,size,publish_date,seeders,quality,score,rejected_reason,status,raw_json);
        CREATE TABLE season_pack_searches(id INTEGER PRIMARY KEY,show_id,season,provider,title,url,guid,size,seeders,quality,score);
        INSERT INTO shows VALUES(1,'Brothers',0,1,'','','','HD',NULL,0,0,0,0,'2009-09-27',NULL,NULL,NULL);
        INSERT INTO episodes VALUES(1,1,1,1,'Wanted',1,0,NULL,0,'2009-09-27');
        ''')
        show_preferences.init(c)
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


def accepted(result):
    return sorted(r['title'] for r in result['results'] if not r['rejected_reason'])


def test_brothers_search_rejects_other_shows_sharing_the_word(store,monkeypatch):
    monkeypatch.setattr(indexer_client,'search',lambda p,q,t:[item(x) for x in BROTHERS_RESULTS])
    grabbed=[]
    monkeypatch.setattr(engine,'grab_result',lambda rid:grabbed.append(rid) or {'ok':True})
    result=engine.search_episode(1,auto_grab=True)
    assert accepted(result)==['Brothers.2009.S01E01.1080p.WEB','Brothers.S01E01.720p.HDTV']
    best=next(r for r in result['results'] if r['id']==grabbed[0])
    assert best['title']=='Brothers.2009.S01E01.1080p.WEB'
    rejected={r['title']:r['rejected_reason'] for r in result['results'] if r['rejected_reason']}
    assert set(rejected)=={'Band.of.Brothers.S01E01.1080p.BluRay','Brothers.and.Sisters.S01E01.1080p.WEB','The.Brothers.Sun.S01E01.1080p.WEB','Brothers.1984.S01E01.1080p'}
    assert all('Not this show' in v for v in rejected.values())


def test_only_other_shows_found_means_nothing_is_grabbed(store,monkeypatch):
    monkeypatch.setattr(indexer_client,'search',lambda p,q,t:[item('Band.of.Brothers.S01E01.1080p')])
    monkeypatch.setattr(engine,'grab_result',lambda *a:pytest.fail('must not grab another show'))
    assert engine.search_episode(1,auto_grab=True)['grabbed'] is None


def test_loose_mode_restores_previous_behaviour_for_the_show_name(store,monkeypatch):
    with dbcore.connect(store) as c:c.execute("UPDATE shows SET search_title_match='loose'")
    monkeypatch.setattr(indexer_client,'search',lambda p,q,t:[item(x) for x in BROTHERS_RESULTS])
    assert len(accepted(engine.search_episode(1)))==len(BROTHERS_RESULTS)


def test_extra_search_names_are_searched_and_accepted(store,monkeypatch):
    with dbcore.connect(store) as c:c.execute("UPDATE shows SET search_aliases='Brothers US'")
    calls=[]
    def search(p,q,t):
        calls.append(q['q'])
        return [item('Brothers.US.S01E01.1080p')] if q['q']=='Brothers US' else [item('Band.of.Brothers.S01E01.1080p')]
    monkeypatch.setattr(indexer_client,'search',search)
    result=engine.search_episode(1)
    assert calls==['Brothers','Brothers US'] and accepted(result)==['Brothers.US.S01E01.1080p']


def test_id_search_is_tried_first_and_skips_name_queries_when_it_finds_the_episode(store,monkeypatch):
    with dbcore.connect(store) as c:c.execute("UPDATE shows SET tvdb_id=83465,imdb_id='tt1355642'")
    monkeypatch.setattr(indexer_client,'capabilities',lambda p,force=False:{'modes':{'tvsearch':['q','season','ep','tvdbid']},'categories':[],'limit':100})
    calls=[]
    def search(p,q,t):
        calls.append(dict(q))
        return [item('Brothers.S01E01.720p.HDTV')] if 'tvdbid' in q else []
    monkeypatch.setattr(indexer_client,'search',search)
    result=engine.search_episode(1)
    assert calls==[{'t':'tvsearch','season':1,'ep':1,'tvdbid':'83465'}]
    assert accepted(result)==['Brothers.S01E01.720p.HDTV'] and result['results'][0]['search_by']=='id'


def test_id_search_can_be_turned_off_and_unsupported_ids_are_not_sent(store,monkeypatch):
    with dbcore.connect(store) as c:c.execute("UPDATE shows SET tvdb_id=83465,search_by_id=0")
    monkeypatch.setattr(indexer_client,'capabilities',lambda p,force=False:{'modes':{'tvsearch':['q','season','ep','tvdbid']},'categories':[],'limit':100})
    calls=[]
    monkeypatch.setattr(indexer_client,'search',lambda p,q,t:calls.append(q) or [])
    engine.search_episode(1)
    assert all('tvdbid' not in q for q in calls)
    assert indexer_client.id_parameters({'url':'https://x.test'},{'tvdb_id':83465,'imdb_id':'tt1355642'})=={'tvdbid':'83465'}
    monkeypatch.setattr(indexer_client,'capabilities',lambda p,force=False:{'modes':{'tvsearch':['q','season','ep']},'categories':[],'limit':100})
    assert indexer_client.id_parameters({'url':'https://x.test'},{'tvdb_id':83465})=={}


def test_failed_id_search_falls_back_to_the_name(store,monkeypatch):
    with dbcore.connect(store) as c:c.execute("UPDATE shows SET tvdb_id=83465")
    monkeypatch.setattr(indexer_client,'capabilities',lambda p,force=False:{'modes':{'tvsearch':['q','season','ep','tvdbid']},'categories':[],'limit':100})
    def search(p,q,t):
        if 'tvdbid' in q:raise indexer_client.IndexerError('rejected',code=201)
        return [item('Brothers.S01E01.720p.HDTV')]
    monkeypatch.setattr(indexer_client,'search',search)
    result=engine.search_episode(1)
    assert accepted(result)==['Brothers.S01E01.720p.HDTV'] and not result['errors']


@pytest.mark.parametrize('title,name,ok',[
    ('Doctor.Who.S01E01','Doctor Who (2005)',True),('Doctor.Who.2005.S01E01','Doctor Who (2005)',True),
    ('Office.S01E01','The Office (US)',True),('The.Office.US.S01E01','The Office (US)',True),
    ('Greys.Anatomy.S01E01','Grey\'s Anatomy',True),('Law.and.Order.S01E01','Law & Order',True),
    ('Marvels.Agents.of.SHIELD.S01E01',"Marvel's Agents of S.H.I.E.L.D.",True),
    ('Law.and.Order.SVU.S01E01','Law & Order',False),('The.Brothers.S01E01','Brothers',False),
    ('Brothers.UK.S01E01','Brothers',False),('Brothers.S01E02','Brothers',False)])
def test_title_matching_rules(title,name,ok):
    assert (search_names.release_rejection(title,name,{},dict(season=1,episode=1)) is None)==ok


def test_year_must_be_the_shows_first_air_year():
    episode=dict(season=1,episode=1)
    assert search_names.release_rejection('Brothers.2009.S01E01','Brothers',{'first_air_date':'2009-09-27'},episode) is None
    assert search_names.release_rejection('Brothers.1984.S01E01','Brothers',{'first_air_date':'2009-09-27'},episode)
    assert search_names.release_rejection('Brothers.2009.S01E01','Brothers',{},episode)


def test_season_pack_search_uses_strict_matching_and_extra_names(store,monkeypatch):
    with dbcore.connect(store) as c:c.execute("UPDATE shows SET search_aliases='Brothers US'")
    monkeypatch.setattr(indexer_client,'search',lambda p,q:[item('Band.of.Brothers.S01.1080p'),item('Brothers.US.S01.1080p')])
    result=production.season_pack_search(1,1)
    assert [r['title'] for r in result['results']]==['Brothers.US.S01.1080p']


def test_preference_validation_and_defaults_exclude_names(store):
    values=show_preferences.options({'search_title_match':'LOOSE','search_aliases':'Brothers US, Brothers 2009\nBrothers US','search_by_id':'0'})
    assert values=={'search_title_match':'loose','search_aliases':'Brothers US\nBrothers 2009','search_by_id':0}
    with pytest.raises(ValueError):show_preferences.options({'search_title_match':'fuzzy'})
    with dbcore.connect(store) as c:
        c.execute("CREATE TABLE settings(section,name,value,is_secret,source,updated_at,UNIQUE(section,name))")
        saved=show_preferences.save_defaults(c,{'search_title_match':'strict','search_aliases':'Brothers US'})
    assert 'search_aliases' not in saved and saved['search_title_match']=='strict'
