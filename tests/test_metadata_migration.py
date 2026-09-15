import json
import pytest
import dbcore
import metadata_migration as migration


@pytest.fixture
def database(tmp_path):
    path=tmp_path/'library.db'
    with dbcore.connect(path) as c:
        c.executescript('''CREATE TABLE shows(id INTEGER PRIMARY KEY,name,name_override,metadata_provider,episode_order,tvdb_id,tmdb_id,scene_numbering,past_episode_status,future_episode_status);
        INSERT INTO shows VALUES(1,'Fixture','My custom name','tvdb','official',50,60,1,'Wanted','Ignored');
        CREATE TABLE episodes(id INTEGER PRIMARY KEY,show_id,season,episode,name,airdate,overview,still_url,tvdb_episode_id,tmdb_episode_id,status,location,scene_season,scene_episode,absolute_number,metadata_updated_at,UNIQUE(show_id,season,episode));
        INSERT INTO episodes VALUES(1,1,1,1,'Pilot','2020-01-01','',NULL,100,200,'Downloaded','/keep/pilot.mkv',NULL,NULL,1,NULL);
        INSERT INTO episodes VALUES(2,1,1,2,'Next','2020-01-02','',NULL,101,201,'Ignored','',NULL,NULL,2,NULL);
        CREATE TABLE downloads(id INTEGER PRIMARY KEY,episode_id,status);
        CREATE TABLE search_results(episode_id,rejected_reason,status);
        INSERT INTO search_results VALUES(1,NULL,'Found');
        CREATE TABLE scene_mappings(show_id,season,episode,alias);
        INSERT INTO scene_mappings VALUES(1,NULL,NULL,'Alias'),(1,1,1,'');
        ''')
    return path


def target():
    return {'provider':'tvdb','order':'dvd','remote_id':50,'name':'New title','episodes':[
        {'remote_id':100,'season':1,'episode':2,'name':'Pilot','airdate':'2020-01-01','overview':'New plot','still_url':None},
        {'remote_id':101,'season':1,'episode':1,'name':'Next','airdate':'2020-01-02','overview':'','still_url':None},
        {'remote_id':102,'season':2,'episode':1,'name':'Future','airdate':'2099-01-01','overview':'','still_url':None}]}


def plan(database,monkeypatch):
    monkeypatch.setattr(migration,'payload',lambda *a:target())
    return migration.preview(database,1,{'provider':'tvdb','order':'dvd','remote_id':50})


def test_dvd_swap_preserves_files_status_ids_history_and_custom_name(database,monkeypatch):
    review=plan(database,monkeypatch)
    assert review['unmatched']==0
    result=migration.apply(database,review,{})
    assert result['updated']==2 and result['added']==1
    with dbcore.connect(database,readonly=True) as c:
        one=dict(c.execute('SELECT * FROM episodes WHERE id=1').fetchone())
        assert (one['episode'],one['location'],one['status'],one['tvdb_episode_id'])==(2,'/keep/pilot.mkv','Downloaded',100)
        assert c.execute('SELECT status FROM episodes WHERE id=2').fetchone()[0]=='Ignored'
        assert c.execute('SELECT status FROM episodes WHERE id=3').fetchone()[0]=='Ignored'
        assert tuple(c.execute('SELECT name,episode_order,scene_numbering FROM shows').fetchone())==('My custom name','dvd',0)
        assert c.execute('SELECT status FROM search_results').fetchone()[0]=='Rejected'
        assert c.execute('SELECT alias FROM scene_mappings').fetchone()[0]=='Alias'
        old=json.loads(c.execute('SELECT previous_json FROM metadata_migrations').fetchone()[0])
        assert old['episodes'][0]['episode']==1


def test_stale_preview_is_rejected_without_any_renumbering(database,monkeypatch):
    review=plan(database,monkeypatch)
    with dbcore.connect(database) as c:c.execute("UPDATE episodes SET status='Wanted' WHERE id=2")
    with pytest.raises(ValueError,match='changed after preview'):migration.apply(database,review,{})
    with dbcore.connect(database,readonly=True) as c:assert c.execute('SELECT episode FROM episodes WHERE id=1').fetchone()[0]==1


def test_active_download_started_after_preview_blocks_change(database,monkeypatch):
    review=plan(database,monkeypatch)
    with dbcore.connect(database) as c:c.execute("INSERT INTO downloads VALUES(1,1,'Queued')")
    with pytest.raises(ValueError,match='active downloads'):migration.apply(database,review,{})


@pytest.mark.parametrize('choices',[{'1':None},{'1':1,'2':1},{'1':99},{'1':'0'}])
def test_unmatched_duplicate_and_invalid_choices_block_everything(database,monkeypatch,choices):
    with pytest.raises(ValueError):migration.apply(database,plan(database,monkeypatch),choices)


def test_missing_identity_requires_matching_title_and_date_or_manual_selection(database,monkeypatch):
    with dbcore.connect(database) as c:c.execute("UPDATE episodes SET tvdb_episode_id=NULL,name='Unknown' WHERE id=1")
    review=plan(database,monkeypatch)
    assert review['unmatched']==1
    with pytest.raises(ValueError):migration.apply(database,review,{})
    assert migration.apply(database,review,{'1':0})['updated']==2


def test_incomplete_provider_response_and_duplicate_ids_are_rejected(monkeypatch,database):
    import tvdb_client
    monkeypatch.setattr(tvdb_client,'show_payload',lambda *a:({'name':'Test'},[]))
    with pytest.raises(ValueError,match='no episodes'):migration.payload(database,{'name':'Test'},{'provider':'tvdb','remote_id':5})
    ep={'id':5,'episode_number':1,'name':'Test'}
    monkeypatch.setattr(tvdb_client,'show_payload',lambda *a:({'name':'Test'},[(1,{'episodes':[ep,ep]})]))
    with pytest.raises(ValueError,match='duplicate'):migration.payload(database,{'name':'Test'},{'provider':'tvdb','remote_id':5})


def test_tmdb_partial_season_failure_leaves_metadata_unchanged(tmp_path,monkeypatch):
    import metadata_service
    database=tmp_path/'refresh.db';monkeypatch.setattr(metadata_service,'DB',database)
    with dbcore.connect(database) as c:
        c.executescript("CREATE TABLE shows(id,name,tmdb_id,tvdb_id,imdb_id,metadata_provider,episode_order);INSERT INTO shows VALUES(1,'Original',42,NULL,NULL,'tmdb','official');")
    def get(path,params):
        if path=='/tv/42':return {'name':'Replacement','seasons':[{'season_number':1},{'season_number':2}]}
        if path.endswith('/1'):return {'episodes':[]}
        raise ValueError('Season request failed')
    monkeypatch.setattr(metadata_service,'_tmdb',get)
    with pytest.raises(ValueError,match='Season request failed'):metadata_service.refresh_show(1)
    with dbcore.connect(database,readonly=True) as c:assert c.execute('SELECT name FROM shows').fetchone()[0]=='Original'
