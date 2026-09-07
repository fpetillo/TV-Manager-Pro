"""Read-only client polling and conservative acquisition status updates."""
import requests
import dbcore
import lifecycle

def nzb_rpc(get,method,params):
    host=get('NZBGet','nzbget_host','').rstrip('/')
    if not host:raise ValueError('NZBGet host is not configured')
    user=get('NZBGet','nzbget_username','');password=get('NZBGet','nzbget_password','')
    r=requests.post(host+'/jsonrpc',json={'method':method,'params':params,'id':1},auth=(user,password) if user else None,timeout=15)
    r.raise_for_status();data=r.json()
    if data.get('error'):raise ValueError('NZBGet RPC rejected '+method)
    return data.get('result')

def transmission_rpc(get,method,arguments):
    host=get('TORRENT','torrent_host','').rstrip('/')
    if not host:raise ValueError('Transmission host is not configured')
    url=host if host.endswith('/rpc') else host+'/transmission/rpc'
    user=get('TORRENT','torrent_username','');password=get('TORRENT','torrent_password','')
    kwargs={'json':{'method':method,'arguments':arguments},'auth':(user,password) if user else None,'timeout':15}
    r=requests.post(url,**kwargs)
    if r.status_code==409:
        token=r.headers.get('X-Transmission-Session-Id')
        if not token:raise ValueError('Transmission did not provide a session ID')
        r=requests.post(url,headers={'X-Transmission-Session-Id':token},**kwargs)
    r.raise_for_status();data=r.json()
    if data.get('result')!='success':raise ValueError('Transmission RPC rejected '+method)
    return data.get('arguments') or {}

def snapshot(client,get):
    out={}
    if client=='NZBGet':
        for row in nzb_rpc(get,'listgroups',[]) or []:
            total=float(row.get('FileSizeMB') or 0);remaining=float(row.get('RemainingSizeMB') or 0)
            out[str(row['NZBID'])]={'status':'Downloading','progress':max(0,min(1,1-remaining/total)) if total else 0}
        for row in nzb_rpc(get,'history',[False]) or []:
            status=str(row.get('Status',''))
            if status.startswith('SUCCESS/'):
                out[str(row['NZBID'])]={'status':'Downloaded','progress':1}
            elif status.startswith(('FAILURE/','DELETED/','WARNING/')):
                out[str(row['NZBID'])]={'status':'Failed','progress':0,'error':'NZBGet: '+status}
    elif client=='Transmission':
        rows=transmission_rpc(get,'torrent-get',{'fields':['hashString','percentDone','error','errorString','status']}).get('torrents',[])
        for row in rows:
            progress=float(row.get('percentDone') or 0)
            # Tracker warnings (1/2) are not terminal; local errors (3) need attention.
            failed=int(row.get('error') or 0)==3
            out[str(row['hashString']).lower()]={'status':'Failed' if failed else 'Downloaded' if progress>=1 else 'Downloading','progress':progress,'error':'Transmission reported a local error' if failed else ''}
    elif client=='Deluge':
        host=get('TORRENT','torrent_host','').rstrip('/')
        if not host:raise ValueError('Deluge host is not configured')
        with requests.Session() as session:
            def rpc(method,params):
                r=session.post(host+'/json',json={'method':method,'params':params,'id':1},timeout=15);r.raise_for_status();d=r.json()
                if d.get('error'):raise ValueError('Deluge RPC rejected '+method)
                return d.get('result')
            if not rpc('auth.login',[get('TORRENT','torrent_password','')]):raise ValueError('Deluge authentication failed')
            if not rpc('web.connected',[]):raise ValueError('Deluge Web is not connected to a daemon')
            rows=rpc('core.get_torrents_status',[{},['progress','state','is_finished']]) or {}
            for tid,row in rows.items():
                progress=float(row.get('progress') or 0)/100
                out[tid.lower()]={'status':'Failed' if row.get('state')=='Error' else 'Downloaded' if row.get('is_finished') or progress>=1 else 'Downloading','progress':progress,'error':'Deluge reported an error' if row.get('state')=='Error' else ''}
    else:raise ValueError('Unsupported polling client')
    return out

def update(db,client,states):
    changed=0;failures=[]
    with dbcore.connect(db) as c:
        for table,kind in [('downloads','episode'),('season_pack_downloads','season_pack')]:
            rows=c.execute(f"SELECT * FROM {table} WHERE client=? AND status IN ('Queued','Downloading','Downloaded')",(client,)).fetchall()
            for row in rows:
                state=states.get(str(row['external_id']).lower())
                if not state:continue
                status=state['status']
                if row['status']=='Downloaded' and status=='Downloading':continue
                if table=='season_pack_downloads':
                    c.execute('UPDATE season_pack_downloads SET progress=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(state.get('progress',0),row['id']))
                if status==row['status']:continue
                lifecycle.transition(kind,row['id'],row['status'],status,message=state.get('error') or client+' '+status,conn=c)
                if table=='downloads':
                    if status=='Downloaded':c.execute('UPDATE downloads SET completed_at=CURRENT_TIMESTAMP WHERE id=?',(row['id'],))
                    if status=='Failed':
                        c.execute('UPDATE downloads SET error=? WHERE id=?',(state.get('error'),row['id']))
                        c.execute("UPDATE episodes SET status='Failed' WHERE id=? AND COALESCE(location,'')=''",(row['episode_id'],))
                else:
                    c.execute('UPDATE season_pack_downloads SET progress=?,error=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(state.get('progress',0),state.get('error'),row['id']))
                    if status=='Failed':
                        c.execute("UPDATE episodes SET status='Failed' WHERE COALESCE(location,'')='' AND id IN (SELECT episode_id FROM acquisition_episode_links WHERE acquisition_type='season_pack' AND acquisition_id=?)",(row['id'],))
                if status=='Failed':failures.append({'message':client+' download failed'})
                changed+=1
    return {'client':client,'checked':len(states),'updated':changed,'failures':failures}
