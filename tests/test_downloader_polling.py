import sqlite3
import pytest
import downloader_polling as polling

def get(section,key,default=''):
    return {'torrent_host':'http://client.test/transmission/rpc','nzbget_host':'http://nzb.test'}.get(key,default)

class Response:
    def __init__(self,data,status=200,headers=None):self.data=data;self.status_code=status;self.headers=headers or {}
    def json(self):return self.data
    def raise_for_status(self):pass

def test_transmission_handshake_and_states(monkeypatch):
    calls=[]
    def post(url,**kwargs):
        calls.append((url,kwargs))
        if len(calls)==1:return Response({},409,{'X-Transmission-Session-Id':'session'})
        return Response({'result':'success','arguments':{'torrents':[{'hashString':'ABC','percentDone':1,'error':2},{'hashString':'BAD','percentDone':0,'error':3}]}})
    monkeypatch.setattr(polling.requests,'post',post)
    rows=polling.snapshot('Transmission',get)
    assert rows['abc']['status']=='Downloaded' and rows['bad']['status']=='Failed'
    assert calls[1][1]['headers']['X-Transmission-Session-Id']=='session'
    assert calls[1][0]=='http://client.test/transmission/rpc'

def test_nzbget_waits_for_postprocess_and_detects_failure(monkeypatch):
    def rpc(get,method,params):
        if method=='listgroups':return [{'NZBID':1,'Status':'UNPACKING','FileSizeMB':100,'RemainingSizeMB':0}]
        return [{'NZBID':2,'Status':'SUCCESS/ALL'},{'NZBID':3,'Status':'FAILURE/UNPACK'}]
    monkeypatch.setattr(polling,'nzb_rpc',rpc)
    rows=polling.snapshot('NZBGet',get)
    assert rows['1']['status']=='Downloading'
    assert rows['2']['status']=='Downloaded' and rows['3']['status']=='Failed'

def test_deluge_login_daemon_and_progress(monkeypatch):
    class Session:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,**kwargs):
            method=kwargs['json']['method']
            return Response({'result':{'HASH':{'state':'Seeding','progress':100,'is_finished':True}} if method=='core.get_torrents_status' else True})
    monkeypatch.setattr(polling.requests,'Session',Session)
    assert polling.snapshot('Deluge',get)['hash']['status']=='Downloaded'

def test_status_updates_preserve_terminal_and_existing_episodes(tmp_path):
    db=tmp_path/'db';c=sqlite3.connect(db)
    c.executescript('''CREATE TABLE downloads(id,client,external_id,status,episode_id,error,completed_at);
    CREATE TABLE episodes(id,status,location);
    CREATE TABLE season_pack_downloads(id,client,external_id,status,progress,error,updated_at);
    CREATE TABLE acquisition_episode_links(acquisition_type,acquisition_id,episode_id);
    CREATE TABLE acquisition_events(acquisition_type,acquisition_id,from_state,to_state,message,details_json);
    INSERT INTO downloads VALUES(1,'Transmission','a','Queued',1,NULL,NULL);
    INSERT INTO downloads VALUES(2,'Transmission','b','Importing',2,NULL,NULL);
    INSERT INTO downloads VALUES(3,'Transmission','c','Downloading',3,NULL,NULL);
    INSERT INTO episodes VALUES(1,'Snatched',''),(2,'Downloaded','existing'),(3,'Downloaded','existing');
    ''');c.commit();c.close()
    states={'a':{'status':'Downloaded','progress':1},'b':{'status':'Downloading','progress':0.5},'c':{'status':'Failed','error':'error','progress':0}}
    assert polling.update(db,'Transmission',states)['updated']==2
    assert polling.update(db,'Transmission',states)['updated']==0
    c=sqlite3.connect(db)
    assert c.execute('SELECT status FROM downloads WHERE id=2').fetchone()[0]=='Importing'
    assert c.execute('SELECT status FROM episodes WHERE id=3').fetchone()[0]=='Downloaded';c.close()

def test_rejected_rpc_is_not_success(monkeypatch):
    monkeypatch.setattr(polling.requests,'post',lambda *a,**kw:Response({'result':'invalid request'}))
    with pytest.raises(ValueError,match='rejected'):polling.transmission_rpc(get,'torrent-add',{})
