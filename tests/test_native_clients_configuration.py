import hashlib
from pathlib import Path
from xmlrpc.client import dumps,loads
import pytest
import native_downloaders as clients
import torrent_metadata
import configuration
import app_paths

TORRENT=b'd4:infod4:name4:test12:piece lengthi16384e6:pieces20:12345678901234567890ee'
HASH=hashlib.sha1(TORRENT[7:-1]).hexdigest()


class Response:
    status_code=200
    def __init__(self,data=None,text='',content=b''):self.data=data;self.text=text;self.content=content
    def json(self):return self.data


class Session:
    def __init__(self,handler):self.handler=handler;self.calls=[];self.auth=None;self.closed=False
    def request(self,method,url,**kw):
        assert kw['allow_redirects'] is False and kw['timeout']==(10,30)
        assert kw.get('verify',True) is True
        self.calls.append((method,url,kw));return self.handler(method,url,kw)
    def close(self):self.closed=True


def getter(section,name,default=''):
    return {'torrent_host':'https://client.test','torrent_username':'user','torrent_password':'secret','torrent_label':'tv','torrent_paused':'1'}.get(name,default)


def test_all_native_clients_reach_main_connection_and_polling_workflows(monkeypatch):
    import engine,downloader_polling
    calls=[]
    monkeypatch.setattr(clients,'run',lambda method,get,action,result=None:calls.append((method,action)) or ({} if action=='snapshot' else {'ok':True,'client':clients.NAMES[method]}))
    monkeypatch.setattr(downloader_polling,'update',lambda db,name,states:{'client':name,'updated':0,'failures':[]})
    for method,name in clients.NAMES.items():
        monkeypatch.setattr(engine,'downloader_config_public',lambda method=method:{'use_nzbs':False,'use_torrents':True,'torrent_method':method,'nzb_method':''})
        assert engine.test_downloaders()==[{'ok':True,'client':name}]
        assert engine.poll_downloaders()['results'][0]['client']==name
        assert calls[-2:]==[(method,'test'),(method,'snapshot')]


def test_deluge_daemon_upload_label_pause_and_no_automatic_replay(monkeypatch):
    import deluge_client
    calls=[];options={}
    class RPC:
        connected=False
        def __init__(self,*a,**kw):options.update(kw)
        def connect(self):self.connected=True
        def disconnect(self):calls.append(('disconnect',))
        def call(self,method,*args):
            calls.append((method,*args))
            return {'core.get_torrents_status':{},'core.get_enabled_plugins':['Label'],'label.get_labels':['tv'],'core.add_torrent_file':HASH}.get(method,'2.2')
    monkeypatch.setattr(deluge_client,'DelugeRPCClient',RPC)
    monkeypatch.setattr(torrent_metadata,'describe',lambda u:(HASH,TORRENT))
    assert clients.run('deluged',getter,'send',{'url':'https://provider.test/file'})==HASH
    upload=next(r for r in calls if r[0]=='core.add_torrent_file')
    assert upload[-1]['add_paused'] is True and options['automatic_reconnect'] is False and options['timeout']==20
    assert ('label.set_torrent',HASH,'tv') in calls and calls[-1]==('disconnect',)


def test_putio_uses_vendor_token_header_and_uploads_descriptor_bytes(monkeypatch):
    def get(section,name,default=''):
        return {'torrent_password':'secret','torrent_path':'15','torrent_paused':'0'}.get(name,default)
    def handler(method,url,kw):
        assert kw['headers']['Authorization']=='Bearer secret'
        assert 'secret' not in url
        if url.endswith('/files/upload'):
            assert kw['files']['file'][1]==TORRENT and kw['data']['parent_id']==15
            return Response({'status':'OK','transfer':{'id':55}})
        if url.endswith('/transfers/list'):
            return Response({'status':'OK','transfers':[{'id':55,'percent_done':100,'status':'COMPLETED'}]})
        return Response({'status':'OK','info':{}})
    session=Session(handler);monkeypatch.setattr(clients.requests,'Session',lambda:session)
    monkeypatch.setattr(torrent_metadata,'describe',lambda u:(HASH,TORRENT))
    assert clients.run('putio',get,'send',{'url':'https://provider.test/file'})=='55'
    assert clients.run('putio',get,'snapshot')['55']['status']=='Downloaded'


def test_exact_torrent_hash_and_magnet_identity(monkeypatch):
    monkeypatch.setattr(torrent_metadata.blackhole,'fetch_payload',lambda *a:TORRENT)
    tid,data=torrent_metadata.describe('https://provider.test/file')
    assert tid==HASH and data==TORRENT
    assert torrent_metadata.describe('magnet:?xt=urn:btih:'+HASH)==(HASH,None)
    with pytest.raises(ValueError):torrent_metadata.describe('magnet:?xt=other')
    with pytest.raises(ValueError):torrent_metadata.blackhole.bdecode(b'd1:bi1e1:ai2ee')


def test_utorrent_token_cookie_session_upload_and_polling(monkeypatch):
    phase={'sent':False}
    def handler(method,url,kw):
        if url.endswith('token.html'):return Response(text='<div id="token">fixture-token</div>')
        params=kw['params'];assert params['token']=='fixture-token'
        if params.get('list'):
            rows=[[HASH,32,'Fixture',100,600]] if phase['sent'] else []
            return Response({'torrents':rows})
        if params['action']=='add-file':assert kw['files']['torrent_file'][1]==TORRENT;phase['sent']=True
        return Response({})
    session=Session(handler);monkeypatch.setattr(clients.requests,'Session',lambda:session)
    monkeypatch.setattr(torrent_metadata,'describe',lambda u:(HASH,TORRENT))
    assert clients.run('utorrent',getter,'send',{'url':'https://provider.test/file'})==HASH
    assert session.auth==('user','secret') and session.closed
    snapshot=clients.run('utorrent',getter,'snapshot')
    assert snapshot[HASH]['progress']==.6 and snapshot[HASH]['status']=='Queued'


def test_rtorrent_xmlrpc_uses_binary_metadata_and_separate_values(monkeypatch):
    methods=[]
    def handler(method,url,kw):
        params,name=loads(kw['data']);methods.append((name,params))
        result=[] if name=='d.multicall2' else '1.0' if name=='system.client_version' else 0
        return Response(content=dumps((result,),methodresponse=True).encode())
    session=Session(handler);monkeypatch.setattr(clients.requests,'Session',lambda:session)
    monkeypatch.setattr(torrent_metadata,'describe',lambda u:(HASH,TORRENT))
    assert clients.run('rtorrent',getter,'send',{'url':'https://provider.test/file'})==HASH
    upload=next(p for n,p in methods if n=='load.raw')
    assert upload[0]=='' and upload[1].data==TORRENT
    assert ('d.custom1.set',(HASH,'tv')) in methods and not any(n=='d.start' for n,p in methods)


def test_synology_discovery_auth_task_identity_and_logout(monkeypatch):
    phase={'sent':False}
    def handler(method,url,kw):
        if url.endswith('query.cgi'):return Response({'success':True,'data':{'SYNO.API.Auth':{'path':'auth.cgi','maxVersion':6},'SYNO.DownloadStation.Task':{'path':'DownloadStation/task.cgi','maxVersion':3}}})
        data=kw['data'];action=data['method']
        if action=='login':return Response({'success':True,'data':{'sid':'session'}})
        assert data['_sid']=='session'
        if action=='create':assert data['uri']=='magnet:fixture';phase['sent']=True
        rows=[{'id':'dbid_9','size':100,'status':'seeding','additional':{'detail':{'uri':'magnet:fixture'},'transfer':{'size_downloaded':100}}}] if phase['sent'] else []
        return Response({'success':True,'data':{'tasks':rows,'total':len(rows)}})
    session=Session(handler);monkeypatch.setattr(clients.requests,'Session',lambda:session)
    assert clients.run('download_station',getter,'send',{'url':'magnet:fixture'})=='dbid_9'
    assert session.calls[-1][2]['data']['method']=='logout'
    assert clients.run('download_station',getter,'snapshot')['dbid_9']['status']=='Downloaded'


@pytest.mark.parametrize('section,name,value',[('General','process_method','delete'),('General','torrent_method','unknown'),('TVManager','background_worker_limit','100'),('General','unpack','perhaps'),('TORRENT','torrent_host','https://user:secret@host')])
def test_invalid_configuration_is_rejected(section,name,value):
    with pytest.raises(ValueError):configuration.validate(section,name,value)


def test_configuration_and_packaged_root(monkeypatch,tmp_path):
    assert configuration.validate('General','unpack','yes')=='1'
    assert configuration.validate('General','torrent_method','utorrent')=='utorrent'
    assert configuration.metadata('General','root_dirs')['control']=='editor'
    monkeypatch.setattr(app_paths.sys,'frozen',True,raising=False)
    monkeypatch.setattr(app_paths.sys,'executable',str(tmp_path/'TVManager.exe'))
    assert app_paths.application_root()==tmp_path
