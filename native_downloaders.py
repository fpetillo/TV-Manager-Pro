"""Native uTorrent, rTorrent HTTP XML-RPC and Synology Download Station clients.

Protocol references and fixture scope are recorded in docs/DOWNLOADER_PROTOCOLS.md.
All client requests retain TLS verification and have bounded request timeouts.
"""
import re
from html.parser import HTMLParser
from urllib.parse import urlparse
from xmlrpc.client import dumps,loads,Binary
import requests
import torrent_metadata

NAMES={'utorrent':'uTorrent','rtorrent':'rTorrent','download_station':'DownloadStation','deluged':'DelugeDaemon','putio':'put.io'}


def ratio(value,total=1):
    return max(0,min(1,float(value or 0)/float(total))) if float(total or 0)>0 else 0


def state(progress,failed=False,complete=False,queued=False):
    return {'status':'Failed' if failed else 'Downloaded' if complete or progress>=1 else 'Queued' if queued else 'Downloading',
            'progress':progress,'error':'Downloader reported an error' if failed else ''}


class TokenParser(HTMLParser):
    def __init__(self):super().__init__();self.inside=False;self.token=''
    def handle_starttag(self,tag,attrs):self.inside=tag=='div' and dict(attrs).get('id')=='token'
    def handle_data(self,data):
        if self.inside:self.token+=data
    def handle_endtag(self,tag):
        if tag=='div':self.inside=False


class Client:
    def __init__(self,get):
        self.get=get;self.host=(get('TORRENT','torrent_host','') or '').rstrip('/')
        parsed=urlparse(self.host)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Enter the downloader HTTP/HTTPS address and use the separate username/password settings.')
        self.session=requests.Session()
    def __enter__(self):return self
    def __exit__(self,*args):self.session.close()
    def request(self,method,url,**kwargs):
        response=self.session.request(method,url,timeout=(10,30),allow_redirects=False,**kwargs)
        if not 200<=response.status_code<300:raise ValueError(f'Downloader returned HTTP {response.status_code}')
        return response
    def option(self,name,default=''):return self.get('TORRENT','torrent_'+name,default) or default
    def paused(self):return str(self.option('paused','0')).lower() in {'1','true','yes','on'}


class UTorrent(Client):
    def connect(self):
        self.base=self.host if self.host.endswith('/gui') else self.host+'/gui'
        self.session.auth=(self.option('username'),self.option('password'))
        parser=TokenParser();parser.feed(self.request('GET',self.base+'/token.html').text)
        self.token=parser.token.strip()
        if not self.token:raise ValueError('uTorrent did not provide an authentication token.')
    def rpc(self,params,files=None):
        data=self.request('POST' if files else 'GET',self.base+'/',params={'token':self.token,**params},**({'files':files} if files else {})).json()
        if data.get('error'):raise ValueError('uTorrent rejected the request.')
        return data
    def snapshot(self):
        return {str(r[0]).lower():state(ratio(r[4],1000),failed=bool(int(r[1])&16),queued=bool(int(r[1])&32)) for r in self.rpc({'list':1}).get('torrents',[])}
    def send(self,result):
        tid,data=torrent_metadata.describe(result['url'])
        if tid in self.snapshot():return tid
        if data:self.rpc({'action':'add-file'},files={'torrent_file':('tvmanager.torrent',data,'application/x-bittorrent')})
        else:self.rpc({'action':'add-url','s':result['url']})
        if self.option('label'):self.rpc({'action':'setprops','hash':tid,'s':'label','v':self.option('label')})
        if self.paused():self.rpc({'action':'pause','hash':tid})
        return tid


class RTorrent(Client):
    def connect(self):self.rpc('system.client_version',[])
    def rpc(self,method,params):
        data=dumps(tuple(params),methodname=method,allow_none=True).encode('utf-8')
        response=self.request('POST',self.host,data=data,headers={'Content-Type':'text/xml'},auth=(self.option('username'),self.option('password')))
        if len(response.content)>20*1024*1024:raise ValueError('rTorrent response exceeds 20 MB')
        try:values,_=loads(response.content);return values[0] if values else None
        except Exception:raise ValueError('rTorrent XML-RPC rejected '+method) from None
    def snapshot(self):
        rows=self.rpc('d.multicall2',['','main','d.hash=','d.completed_bytes=','d.size_bytes=','d.complete=','d.is_active=','d.message=']) or []
        # Tracker messages are warnings, not proof of a failed media download.
        return {str(r[0]).lower():state(ratio(r[1],r[2]),complete=bool(r[3]),queued=not bool(r[4])) for r in rows}
    def send(self,result):
        tid,data=torrent_metadata.describe(result['url'])
        if tid in self.snapshot():return tid
        self.rpc('load.raw' if data else 'load.normal',['',Binary(data) if data else result['url']])
        if self.option('path'):self.rpc('d.directory.set',[tid,self.option('path')])
        if self.option('label'):self.rpc('d.custom1.set',[tid,self.option('label')])
        if not self.paused():self.rpc('d.start',[tid])
        return tid


class DownloadStation(Client):
    def connect(self):
        info=self.request('GET',self.host+'/webapi/query.cgi',params={'api':'SYNO.API.Info','version':1,'method':'query','query':'SYNO.API.Auth,SYNO.DownloadStation.Task'}).json()
        if not info.get('success'):raise ValueError('Download Station API discovery failed')
        self.apis=info['data'];self.sid=''
        login=self.rpc('SYNO.API.Auth','login',account=self.option('username'),passwd=self.option('password'),session='DownloadStation',format='sid')
        self.sid=login.get('sid')
        if not self.sid:raise ValueError('Download Station login failed')
    def rpc(self,api,method,**params):
        spec=self.apis.get(api) or {};path=spec.get('path','')
        if not path or not re.fullmatch(r'[A-Za-z0-9_./-]+',path) or '..' in path or path.startswith('/'):
            raise ValueError('Download Station returned an invalid API path')
        version=min(int(spec.get('maxVersion',1)),6 if api=='SYNO.API.Auth' else 3)
        response=self.request('POST',self.host+'/webapi/'+path,data={'api':api,'method':method,'version':version,'_sid':self.sid,**params}).json()
        if not response.get('success'):raise ValueError('Download Station rejected '+method+' (code '+str((response.get('error') or {}).get('code','unknown'))+')')
        return response.get('data') or {}
    def tasks(self):
        result=[];offset=0
        while offset<10000:
            page=self.rpc('SYNO.DownloadStation.Task','list',offset=offset,limit=500,additional='detail,transfer');rows=page.get('tasks') or []
            result.extend(rows);offset+=len(rows)
            if not rows or offset>=int(page.get('total',offset)):return result
        raise ValueError('Download Station queue exceeds the 10,000 item polling limit')
    def snapshot(self):
        result={}
        for r in self.tasks():
            transfer=(r.get('additional') or {}).get('transfer') or {}
            result[str(r['id']).lower()]=state(ratio(transfer.get('size_downloaded'),r.get('size')),failed=r.get('status')=='error',complete=r.get('status') in {'finished','seeding'},queued=r.get('status') in {'waiting','paused'})
        return result
    def send(self,result):
        def matching():return [r for r in self.tasks() if ((r.get('additional') or {}).get('detail') or {}).get('uri')==result['url']]
        matches=matching()
        if len(matches)==1:return str(matches[0]['id'])
        if matches:raise ValueError('Multiple Download Station tasks match this release; review the queue.')
        params={'uri':result['url']}
        if self.option('path'):params['destination']=re.sub(r'^/volume[0-9]+/','',self.option('path')).lstrip('/')
        self.rpc('SYNO.DownloadStation.Task','create',**params)
        matches=matching()
        if len(matches)!=1:raise ValueError('Download Station accepted the request but its task ID needs review.')
        tid=str(matches[0]['id'])
        if self.paused():self.rpc('SYNO.DownloadStation.Task','pause',id=tid)
        return tid
    def __exit__(self,*args):
        try:
            if getattr(self,'sid',None):self.rpc('SYNO.API.Auth','logout',session='DownloadStation')
        except Exception:pass
        super().__exit__(*args)


class DelugeDaemon(Client):
    def connect(self):
        from deluge_client import DelugeRPCClient
        parsed=urlparse(self.host)
        # Deluge's native RPC uses its own TLS protocol and daemon certificate.
        self.rpc_client=DelugeRPCClient(parsed.hostname,parsed.port or 58846,self.option('username'),self.option('password'),
                                        decode_utf8=True,automatic_reconnect=False,timeout=20)
        self.rpc_client.connect()
        if not self.rpc_client.connected:raise ValueError('Deluge daemon authentication failed')
        self.rpc_client.call('daemon.info')
    def rpc(self,method,*args):return self.rpc_client.call(method,*args)
    def snapshot(self):
        rows=self.rpc('core.get_torrents_status',{},['progress','state','is_finished']) or {}
        return {str(tid).lower():state(ratio(row.get('progress'),100),failed=row.get('state')=='Error',
                complete=bool(row.get('is_finished')) or row.get('state')=='Seeding',queued=row.get('state') in {'Paused','Queued'}) for tid,row in rows.items()}
    def send(self,result):
        import base64
        tid,data=torrent_metadata.describe(result['url'])
        if tid in self.snapshot():return tid
        label=self.option('label').strip().lower()
        if label:
            if not re.fullmatch(r'[a-z0-9_-]+',label):raise ValueError('Deluge labels use lowercase letters, numbers, underscores or hyphens')
            if 'Label' not in self.rpc('core.get_enabled_plugins'):raise ValueError('Enable the Deluge Label plugin before using a download label')
            if label not in self.rpc('label.get_labels'):self.rpc('label.add',label)
        options={'add_paused':self.paused()}
        if self.option('path'):options['download_location']=self.option('path')
        accepted=self.rpc('core.add_torrent_file','tvmanager.torrent',base64.b64encode(data).decode('ascii'),options) if data else self.rpc('core.add_torrent_magnet',result['url'],options)
        if not accepted:raise ValueError('Deluge daemon did not return a torrent ID; review its queue')
        accepted=str(accepted).lower()
        if accepted!=tid:raise ValueError('Deluge returned a different torrent identity; review its queue')
        if label:self.rpc('label.set_torrent',accepted,label)
        return accepted
    def __exit__(self,*args):
        try:
            if getattr(self,'rpc_client',None):self.rpc_client.disconnect()
        finally:super().__exit__(*args)


class PutIO(Client):
    def __init__(self,get):
        # Fixed vendor endpoint; imported SickChill password holds the OAuth token.
        super().__init__(lambda section,key,default='':'https://api.put.io/v2' if key=='torrent_host' else get(section,key,default))
        self.headers={'Authorization':'Bearer '+self.option('password')}
    def rpc(self,method,path,**kwargs):
        value=self.request(method,self.host+path,headers=self.headers,**kwargs).json()
        if value.get('status')!='OK':raise ValueError('put.io rejected the request; check account access and quota')
        return value
    def connect(self):
        if not self.option('password'):raise ValueError('Set the put.io OAuth token in the torrent password field')
        self.rpc('GET','/account/info')
    def snapshot(self):
        result={}
        for item in self.rpc('GET','/transfers/list').get('transfers',[]):
            result[str(item['id'])]=state(ratio(item.get('percent_done'),100),failed=item.get('status') in {'ERROR','CANCELLED'},
                complete=item.get('status') in {'COMPLETED','SEEDING'},queued=item.get('status') in {'IN_QUEUE','WAITING','STOPPED'})
        return result
    def send(self,result):
        if self.paused():raise ValueError('put.io transfer creation does not support the paused option. Turn it off before sending.')
        parent=self.option('path')
        if parent and not str(parent).isdigit():raise ValueError('For put.io, torrent_path is a numeric destination folder ID')
        parent=int(parent or 0)
        if not parent and self.option('username'):
            matches=[f for f in self.rpc('GET','/files/list',params={'parent_id':0}).get('files',[]) if f.get('name')==self.option('username') and f.get('content_type')=='application/x-directory']
            if len(matches)!=1:raise ValueError('The put.io destination folder name is missing or ambiguous; use its numeric folder ID')
            parent=int(matches[0]['id'])
        tid,data=torrent_metadata.describe(result['url'])
        if data:
            value=self.request('POST','https://upload.put.io/v2/files/upload',headers=self.headers,params={'torrent':'true'},
                data={'parent_id':parent},files={'file':('tvmanager.torrent',data,'application/x-bittorrent')}).json()
            if value.get('status')!='OK':raise ValueError('put.io rejected the torrent upload')
        else:value=self.rpc('POST','/transfers/add',data={'url':result['url'],'save_parent_id':parent})
        identity=(value.get('transfer') or {}).get('id')
        if not identity:raise ValueError('put.io did not return a transfer ID; review its transfers before retrying')
        return str(identity)


CLASSES={'utorrent':UTorrent,'rtorrent':RTorrent,'download_station':DownloadStation,'deluged':DelugeDaemon,'putio':PutIO}


def run(method,get,action,result=None):
    with CLASSES[method](get) as client:
        client.connect()
        if action=='send':return client.send(result)
        snapshot=client.snapshot()
        return {'ok':True,'client':NAMES[method],'queue_items':len(snapshot)} if action=='test' else snapshot
