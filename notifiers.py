"""Native notification payloads; credentials stay masked in public responses."""
from pathlib import Path
from urllib.parse import urlparse
import requests
import dbcore

DB=Path(__file__).resolve().parent/'tvmanager.db'
MASK='********'
KINDS={'discord','slack','telegram','gotify','pushover','pushbullet'}
EVENTS={'snatched','downloaded','failed','subtitle'}

def init():
    with dbcore.connect(DB) as c:
        c.execute('''CREATE TABLE IF NOT EXISTS notification_services(
            id INTEGER PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,
            url TEXT DEFAULT '',token TEXT DEFAULT '',recipient TEXT DEFAULT '',
            enabled INTEGER DEFAULT 0,events TEXT DEFAULT 'snatched,downloaded,failed,subtitle',
            last_result TEXT DEFAULT '',last_sent_at TEXT)''')

def listing():
    with dbcore.connect(DB,readonly=True) as c:rows=[dict(r) for r in c.execute('SELECT * FROM notification_services ORDER BY name')]
    for row in rows:
        row['host']=urlparse(row['url']).hostname or ''
        for key in ('url','token','recipient'):row[key]=MASK if row[key] else ''
    return rows

def save(body):
    with dbcore.connect(DB) as c:
        old=c.execute('SELECT * FROM notification_services WHERE id=?',(body.get('id'),)).fetchone()
        if body.get('id') and not old:raise ValueError('Notification service not found')
        value=dict(old) if old else {'url':'','token':'','recipient':'','enabled':0,'events':','.join(sorted(EVENTS))}
        if old and body.get('kind',old['kind'])!=old['kind']:
            for key in ('url','token','recipient'):value[key]=''
        for key in ('name','kind','url','token','recipient','events'):
            if key in body and body[key]!=MASK:value[key]=str(body[key] or '').strip()
        value['enabled']=int(body.get('enabled',value['enabled']) in (True,1,'1','true'))
        if not value.get('name'):raise ValueError('Enter a notification name')
        if value.get('kind') not in KINDS:raise ValueError('Unsupported notification service')
        events={x.strip() for x in value['events'].split(',') if x.strip()}
        if not events or not events<=EVENTS:raise ValueError('Choose supported notification events')
        kind=value['kind']
        if kind in {'slack','discord','gotify'}:
            url=urlparse(value['url'])
            if url.scheme not in {'http','https'} or not url.hostname or url.username or url.password:raise ValueError('Enter a complete HTTP or HTTPS service URL')
            if kind in {'slack','discord'} and url.scheme!='https':raise ValueError('Webhook URL must use HTTPS')
        if kind in {'telegram','gotify','pushover','pushbullet'} and not value['token']:raise ValueError('Enter the service token')
        if kind in {'telegram','pushover'} and not value['recipient']:raise ValueError('Enter the chat ID or user key')
        values=[value[k] for k in ('name','kind','url','token','recipient','enabled','events')]
        if old:c.execute('UPDATE notification_services SET name=?,kind=?,url=?,token=?,recipient=?,enabled=?,events=? WHERE id=?',values+[old['id']]);sid=old['id']
        else:sid=c.execute('INSERT INTO notification_services(name,kind,url,token,recipient,enabled,events) VALUES(?,?,?,?,?,?,?)',values).lastrowid
    return sid

def remove(sid):
    with dbcore.connect(DB) as c:
        if not c.execute('DELETE FROM notification_services WHERE id=?',(sid,)).rowcount:raise ValueError('Notification service not found')

def send(service,event,payload):
    kind=service['kind'];title='TV Manager: '+event
    # Only selected human-readable fields leave the app, never config/path objects.
    description=str(payload.get('show') or payload.get('release') or payload.get('message') or 'TV Manager notification')
    if payload.get('season') is not None and payload.get('episode') is not None:description+=f" S{int(payload['season']):02d}E{int(payload['episode']):02d}"
    text=title+'\n'+description
    headers={}
    if kind=='discord':url=service['url'];data={'content':text[:2000],'allowed_mentions':{'parse':[]}}
    elif kind=='slack':url=service['url'];data={'text':text[:4000],'mrkdwn':False,'link_names':False}
    elif kind=='telegram':url='https://api.telegram.org/bot'+service['token']+'/sendMessage';data={'chat_id':service['recipient'],'text':text[:4096]}
    elif kind=='gotify':url=service['url'].rstrip('/')+'/message';headers={'X-Gotify-Key':service['token']};data={'title':title,'message':description[:4000],'priority':5}
    elif kind=='pushover':url='https://api.pushover.net/1/messages.json';data={'token':service['token'],'user':service['recipient'],'title':title,'message':description[:1024]}
    elif kind=='pushbullet':url='https://api.pushbullet.com/v2/pushes';headers={'Access-Token':service['token']};data={'type':'note','title':title,'body':description[:4000]}
    else:raise ValueError('Unsupported notification service')
    try:
        response=requests.post(url,json=data,headers=headers,timeout=12,allow_redirects=False)
        if not 200<=response.status_code<300:return {'ok':False,'message':f'Service returned HTTP {response.status_code}'}
        if kind=='telegram' and not response.json().get('ok'):return {'ok':False,'message':'Telegram rejected the message'}
        if kind=='pushover' and response.json().get('status')!=1:return {'ok':False,'message':'Pushover rejected the message'}
        return {'ok':True,'message':'Delivered'}
    except (requests.RequestException,ValueError):return {'ok':False,'message':'Delivery failed; check service availability and credentials'}

def dispatch(event,payload,only_id=None):
    with dbcore.connect(DB,readonly=True) as c:
        rows=c.execute('SELECT * FROM notification_services WHERE id=?',(only_id,)).fetchall() if only_id else c.execute('SELECT * FROM notification_services WHERE enabled=1').fetchall()
    if only_id and not rows:raise ValueError('Notification service not found')
    results=[]
    for row in rows:
        if not only_id and event not in {x.strip() for x in row['events'].split(',')}:continue
        result=send(dict(row),event,payload)
        with dbcore.connect(DB) as c:c.execute('UPDATE notification_services SET last_result=?,last_sent_at=CURRENT_TIMESTAMP WHERE id=?',(result['message'],row['id']))
        results.append({'id':row['id'],'name':row['name'],**result})
    return results
