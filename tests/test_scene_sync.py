import sqlite3
import pytest
import scene_sync

@pytest.fixture
def store(tmp_path,monkeypatch):
    db=tmp_path/'db';monkeypatch.setattr(scene_sync,'DB',db);scene_sync.init()
    c=sqlite3.connect(db);c.executescript('''CREATE TABLE shows(id,tvdb_id,episode_order);INSERT INTO shows VALUES(1,123,'official');
    CREATE TABLE episodes(id,show_id,season,episode,scene_season,scene_episode,absolute_number);
    INSERT INTO episodes VALUES(1,1,1,1,NULL,NULL,1),(2,1,1,2,NULL,NULL,2);''');c.commit();c.close()
    return db

def payload():return {'result':'success','data':[{'tvdb':{'season':1,'episode':1,'absolute':1},'scene':{'season':2,'episode':3,'absolute':13}},{'tvdb':{'season':1,'episode':2,'absolute':2},'scene':{'season':2,'episode':3,'absolute':13}}]}

def test_refresh_cache_forward_and_reverse(store,monkeypatch):
    calls=[]
    class Response:
        def raise_for_status(self):pass
        def json(self):return payload()
    monkeypatch.setattr(scene_sync.requests,'get',lambda *a,**k:calls.append(k) or Response())
    assert scene_sync.refresh(1)['mappings']==2
    assert scene_sync.refresh(1)['cached'] and len(calls)==1
    assert calls[0]['params']=={'id':123,'origin':'tvdb','destination':'scene'}
    e=scene_sync.for_search(1,{'season':1,'episode':1})
    assert (e['scene_season'],e['scene_episode'],e['absolute_number'])==(2,3,13)
    c=sqlite3.connect(store);c.row_factory=sqlite3.Row
    assert [r['id'] for r in scene_sync.episode_rows(c,1,2,3)]==[1,2];c.close()

def test_manual_override_and_failed_refresh_preserve_cache(store,monkeypatch):
    class Response:
        def raise_for_status(self):pass
        def json(self):return payload()
    monkeypatch.setattr(scene_sync.requests,'get',lambda *a,**k:Response());scene_sync.refresh(1)
    original={'season':1,'episode':1,'scene_season':8,'scene_episode':9}
    assert scene_sync.for_search(1,original)==original
    monkeypatch.setattr(Response,'json',lambda self:{'result':'failure','data':[]})
    with pytest.raises(ValueError,match='preserved'):scene_sync.refresh(1,force=True)
    assert scene_sync.for_search(1,{'season':1,'episode':1})['scene_episode']==3

def test_double_mapping_and_bad_payload():
    data=payload();data['data'][0]['scene_2']={'season':2,'episode':4,'absolute':14}
    assert len(scene_sync.parse(data))==3
    data['data'][0]['scene']['episode']='not a number'
    with pytest.raises(ValueError):scene_sync.parse(data)


def test_dvd_order_ignores_aired_cache_but_keeps_manual_overrides(store,monkeypatch):
    c=sqlite3.connect(store)
    c.execute("UPDATE shows SET episode_order='dvd'")
    c.execute('INSERT INTO xem_mappings VALUES(1,1,1,2,3,1,13)')
    c.commit();c.row_factory=sqlite3.Row
    monkeypatch.setattr(scene_sync.requests,'get',lambda *a,**k:pytest.fail('Must not fetch aired mappings for DVD'))
    with pytest.raises(ValueError,match='aired episode order'):scene_sync.refresh(1,force=True)
    original={'season':1,'episode':1}
    assert scene_sync.for_search(1,original)==original
    assert scene_sync.episode_rows(c,1,2,3)==[]
    assert [r['id'] for r in scene_sync.episode_rows(c,1,1,1)]==[1]
    c.execute('UPDATE episodes SET scene_season=2,scene_episode=3 WHERE id=2');c.commit()
    assert [r['id'] for r in scene_sync.episode_rows(c,1,2,3)]==[2]
    c.close()
