import sqlite3
import pytest
import tvdb_client as tvdb

def test_search_uses_series_filter_and_maps_ids(monkeypatch):
    calls=[]
    monkeypatch.setattr(tvdb,'get',lambda *args:calls.append(args) or {'data':[{'tvdb_id':'123','name':'Test','image_url':'https://example.test/image'}]})
    result=tvdb.search('Test',2020)
    assert result[0]['tvdb_id']==123 and result[0]['metadata_provider']=='tvdb'
    assert calls[0][1]['type']=='series' and calls[0][1]['year']==2020

def test_paginated_translated_episodes(monkeypatch):
    calls=[]
    def get(path,params,db):
        calls.append((path,params))
        if path.endswith('extended'):return {'data':{'name':'Test','translations':{'nameTranslations':[{'language':'fra','name':'French title'}]}}}
        page=params['page']
        return {'data':{'episodes':[{'id':page+1,'seasonNumber':1,'number':page+1,'name':'Episode'}]},'links':{'next':'next' if page==0 else None}}
    monkeypatch.setattr(tvdb,'get',get)
    info,seasons=tvdb.show_payload({'tvdb_id':123,'metadata_language':'fr-FR'})
    assert info['name']=='French title' and len(seasons[0][1]['episodes'])==2
    assert calls[1][0].endswith('/official/fra')

def test_repeated_pages_are_rejected(monkeypatch):
    monkeypatch.setattr(tvdb,'get',lambda path,*args:{'data':{'name':'Test'}} if path.endswith('extended') else {'data':{'episodes':[{'id':1}]},'links':{'next':'next'}})
    with pytest.raises(ValueError,match='pagination'):tvdb.show_payload({'tvdb_id':1})

def test_refresh_preserves_downloaded_paths_and_checks_identity(tmp_path,monkeypatch):
    db=tmp_path/'db';c=sqlite3.connect(db)
    c.executescript('''CREATE TABLE shows(id,tvdb_id,metadata_provider,name,overview,poster,first_air_date,network,genre);
    INSERT INTO shows VALUES(1,123,'tvdb','Test','','','','','');
    CREATE TABLE episodes(id INTEGER PRIMARY KEY,show_id,season,episode,name,overview,airdate,still_url,tvdb_episode_id,status,metadata_updated_at,location);
    INSERT INTO episodes VALUES(1,1,1,1,'Old','','',NULL,42,'Downloaded',NULL,'/library/keep.mkv');
    CREATE TABLE metadata_refresh_state(show_id INTEGER PRIMARY KEY,last_refresh,last_status,last_error,updated_at);''');c.commit();c.close()
    info={'name':'New','overview':'Overview','first_air_date':'2020-01-01','networks':[],'genres':[]}
    episodes=[(1,{'episodes':[{'id':42,'episode_number':1,'name':'Pilot','overview':'Plot','air_date':'2020-01-01','image':None},{'id':43,'episode_number':2,'name':'Next','overview':'','air_date':'2099-01-01','image':None}]})]
    monkeypatch.setattr(tvdb,'show_payload',lambda *args:(info,episodes))
    show={'id':1,'tvdb_id':123,'future_episode_status':'Skipped'}
    assert tvdb.refresh_show(show,db)['inserted']==1
    c=sqlite3.connect(db);assert c.execute('SELECT status,location FROM episodes WHERE id=1').fetchone()==('Downloaded','/library/keep.mkv');assert c.execute('SELECT status FROM episodes WHERE id=2').fetchone()[0]=='Skipped';c.close()
    episodes[0][1]['episodes'][0]['id']=999
    with pytest.raises(ValueError,match='identity'):tvdb.refresh_show(show,db)

def test_auth_errors_are_sanitized(monkeypatch):
    import requests
    monkeypatch.setattr(tvdb,'credentials',lambda db:('secret','pin'))
    def fail(*a,**kw):raise requests.ConnectionError('contains secret')
    monkeypatch.setattr(tvdb.requests,'post',fail)
    with pytest.raises(ValueError) as exc:tvdb.token(force=True)
    assert 'secret' not in str(exc.value)
