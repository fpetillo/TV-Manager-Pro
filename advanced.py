from __future__ import annotations
import dbcore
import base64, json, re, sqlite3
from pathlib import Path
from urllib.parse import urljoin
import requests

BASE=Path(__file__).resolve().parent
DB=BASE/"tvmanager.db"

def cx():
    return dbcore.connect(DB)

def init():
    with cx() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS provider_definitions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          protocol TEXT NOT NULL DEFAULT 'newznab',
          url TEXT NOT NULL,
          api_key TEXT,
          categories TEXT,
          enabled INTEGER DEFAULT 1,
          priority INTEGER DEFAULT 100,
          minimum_seeders INTEGER DEFAULT 0,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS scene_mappings(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          show_id INTEGER NOT NULL,
          season INTEGER,
          episode INTEGER,
          scene_season INTEGER,
          scene_episode INTEGER,
          absolute_number INTEGER,
          alias TEXT,
          source TEXT DEFAULT 'manual',
          UNIQUE(show_id,season,episode,alias)
        );
        CREATE TABLE IF NOT EXISTS show_groups(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          sort_order INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS show_group_members(
          group_id INTEGER NOT NULL,
          show_id INTEGER NOT NULL,
          PRIMARY KEY(group_id,show_id)
        );
        CREATE TABLE IF NOT EXISTS webhooks(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          url TEXT NOT NULL,
          enabled INTEGER DEFAULT 1,
          event_types TEXT DEFAULT 'downloaded,failed,snatched',
          secret TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS media_servers(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          kind TEXT NOT NULL,
          url TEXT NOT NULL,
          token TEXT,
          username TEXT,
          password TEXT,
          enabled INTEGER DEFAULT 1,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS backup_history(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          path TEXT,
          kind TEXT,
          status TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cols={r["name"] for r in c.execute("PRAGMA table_info(episodes)").fetchall()}
        for name,definition in {
            "absolute_number":"INTEGER",
            "scene_season":"INTEGER",
            "scene_episode":"INTEGER",
            "subtitle_status":"TEXT",
        }.items():
            if name not in cols:c.execute(f'ALTER TABLE episodes ADD COLUMN "{name}" {definition}')
        c.commit()

def split_multi_episode(title):
    t=str(title)
    # S01E01E02 / S01E01-E03 / 1x01-1x03
    m=re.search(r"(?i)S(\d{1,2})E(\d{1,3})(?:E|-E?)(\d{1,3})",t)
    if m:
        s,a,b=map(int,m.groups());return [(s,e) for e in range(min(a,b),max(a,b)+1)]
    m=re.search(r"(?i)\b(\d{1,2})x(\d{1,3})-(?:\1x)?(\d{1,3})\b",t)
    if m:
        s,a,b=map(int,m.groups());return [(s,e) for e in range(min(a,b),max(a,b)+1)]
    m=re.search(r"(?i)S(\d{1,2})E(\d{1,3})",t)
    if m:return [(int(m.group(1)),int(m.group(2)))]
    m=re.search(r"(?i)\b(\d{1,2})x(\d{1,3})\b",t)
    if m:return [(int(m.group(1)),int(m.group(2)))]
    return []

def aliases(show_id):
    with cx() as c:
        rows=c.execute("""SELECT DISTINCT alias FROM scene_mappings WHERE show_id=? AND alias IS NOT NULL AND trim(alias)<>'' ORDER BY alias""",(show_id,)).fetchall()
        extra=c.execute("SELECT exception_name AS alias FROM scene_exceptions WHERE show_id=? ORDER BY id",(show_id,)).fetchall()
    return list(dict.fromkeys(r["alias"] for r in list(rows)+list(extra)))

def mappings(show_id):
    with cx() as c:
        rows=[dict(r) for r in c.execute("SELECT * FROM scene_mappings WHERE show_id=? ORDER BY season,episode,alias",(show_id,)).fetchall()]
        if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='xem_mappings'").fetchone():
            rows.extend(dict(r,source="xem",alias="",id=None) for r in c.execute("SELECT * FROM xem_mappings WHERE show_id=? ORDER BY season,episode,scene_episode",(show_id,)))
        return rows

def save_mapping(show_id,d):
    with cx() as c:
        c.execute("""INSERT INTO scene_mappings(show_id,season,episode,scene_season,scene_episode,absolute_number,alias,source)
                     VALUES(?,?,?,?,?,?,?,'manual')""",
                  (show_id,d.get("season"),d.get("episode"),d.get("scene_season"),d.get("scene_episode"),d.get("absolute_number"),d.get("alias")))
        if d.get("season") is not None and d.get("episode") is not None:
            c.execute("""UPDATE episodes SET scene_season=?,scene_episode=?,absolute_number=COALESCE(?,absolute_number)
                         WHERE show_id=? AND season=? AND episode=?""",
                      (d.get("scene_season"),d.get("scene_episode"),d.get("absolute_number"),show_id,d.get("season"),d.get("episode")))
        c.commit()

def delete_mapping(mid):
    with cx() as c:c.execute("DELETE FROM scene_mappings WHERE id=?",(mid,));c.commit()


def provider_defs_raw():
    with cx() as c:return [dict(r) for r in c.execute("SELECT * FROM provider_definitions WHERE enabled=1 ORDER BY priority,name").fetchall()]


def provider_defs():
    with cx() as c:return [dict(r)|{"api_key":"••••••••" if r["api_key"] else ""} for r in c.execute("SELECT * FROM provider_definitions ORDER BY priority,name").fetchall()]

def save_provider(d):
    with cx() as c:
        if d.get("id"):
            old=c.execute("SELECT api_key FROM provider_definitions WHERE id=?",(d["id"],)).fetchone()
            key=old["api_key"] if d.get("api_key")=="••••••••" and old else d.get("api_key","")
            c.execute("""UPDATE provider_definitions SET name=?,protocol=?,url=?,api_key=?,categories=?,enabled=?,priority=?,minimum_seeders=? WHERE id=?""",
                      (d["name"],d.get("protocol","newznab"),d["url"],key,d.get("categories",""),
                       1 if d.get("enabled",True) else 0,int(d.get("priority",100)),int(d.get("minimum_seeders",0)),d["id"]))
            pid=d["id"]
        else:
            cur=c.execute("""INSERT INTO provider_definitions(name,protocol,url,api_key,categories,enabled,priority,minimum_seeders)
                             VALUES(?,?,?,?,?,?,?,?)""",
                          (d["name"],d.get("protocol","newznab"),d["url"],d.get("api_key",""),d.get("categories",""),
                           1 if d.get("enabled",True) else 0,int(d.get("priority",100)),int(d.get("minimum_seeders",0))))
            pid=cur.lastrowid
        c.commit();return pid

def delete_provider(pid):
    with cx() as c:c.execute("DELETE FROM provider_definitions WHERE id=?",(pid,));c.commit()

def test_provider(pid):
    with cx() as c:p=c.execute("SELECT * FROM provider_definitions WHERE id=?",(pid,)).fetchone()
    if not p:raise ValueError("Provider not found")
    params={"t":"caps"}
    if p["api_key"]:params["apikey"]=p["api_key"]
    r=requests.get(p["url"].rstrip("/")+"/api",params=params,timeout=15,headers={"User-Agent":"TVManager/6.0"})
    r.raise_for_status()
    return {"ok":True,"status":r.status_code,"bytes":len(r.content)}

def groups():
    with cx() as c:
        rows=c.execute("""SELECT g.*,COUNT(m.show_id) show_count FROM show_groups g LEFT JOIN show_group_members m ON m.group_id=g.id GROUP BY g.id ORDER BY sort_order,name""").fetchall()
    return [dict(r) for r in rows]

def save_group(name,show_ids=None, group_id=None, sort_order=None):
    name=(name or "New Group").strip() or "New Group"
    with cx() as c:
        if group_id:
            c.execute("UPDATE show_groups SET name=?,sort_order=COALESCE(?,sort_order) WHERE id=?",(name,sort_order,int(group_id)))
            gid=int(group_id)
        else:
            c.execute("INSERT OR IGNORE INTO show_groups(name) VALUES(?)",(name,))
            gid=c.execute("SELECT id FROM show_groups WHERE name=?",(name,)).fetchone()["id"]
            if sort_order is not None:
                c.execute("UPDATE show_groups SET sort_order=? WHERE id=?",(int(sort_order),gid))
        if show_ids is not None:
            c.execute("DELETE FROM show_group_members WHERE group_id=?",(gid,))
            c.executemany("INSERT OR IGNORE INTO show_group_members(group_id,show_id) VALUES(?,?)",[(gid,int(x)) for x in show_ids])
        c.commit();return gid

def group_shows(gid):
    with cx() as c:
        return [dict(r) for r in c.execute("""SELECT s.* FROM shows s JOIN show_group_members m ON m.show_id=s.id WHERE m.group_id=? ORDER BY s.name COLLATE NOCASE""",(gid,)).fetchall()]

def webhooks():
    with cx() as c:return [dict(r)|{"secret":"••••••••" if r["secret"] else ""} for r in c.execute("SELECT * FROM webhooks ORDER BY name").fetchall()]

def save_webhook(d):
    with cx() as c:
        if d.get("id"):
            old=c.execute("SELECT secret FROM webhooks WHERE id=?",(d["id"],)).fetchone()
            secret=old["secret"] if d.get("secret")=="••••••••" and old else d.get("secret","")
            c.execute("UPDATE webhooks SET name=?,url=?,enabled=?,event_types=?,secret=? WHERE id=?",
                      (d["name"],d["url"],1 if d.get("enabled",True) else 0,d.get("event_types",""),secret,d["id"]))
            wid=d["id"]
        else:
            cur=c.execute("INSERT INTO webhooks(name,url,enabled,event_types,secret) VALUES(?,?,?,?,?)",
                          (d["name"],d["url"],1 if d.get("enabled",True) else 0,d.get("event_types",""),d.get("secret","")))
            wid=cur.lastrowid
        c.commit();return wid

def delete_webhook(wid):
    with cx() as c:
        cur=c.execute("DELETE FROM webhooks WHERE id=?",(int(wid),))
        c.commit()
    if cur.rowcount == 0:
        raise ValueError("Webhook not found")
    return {"ok": True, "deleted": int(wid)}

def delete_group(gid):
    with cx() as c:
        c.execute("DELETE FROM show_group_members WHERE group_id=?",(int(gid),))
        cur=c.execute("DELETE FROM show_groups WHERE id=?",(int(gid),))
        c.commit()
    if cur.rowcount == 0:
        raise ValueError("Show group not found")
    return {"ok": True, "deleted": int(gid)}

def fire_webhooks(event_type,payload):
    with cx() as c:rows=c.execute("SELECT * FROM webhooks WHERE enabled=1").fetchall()
    out=[]
    for w in rows:
        events=[x.strip() for x in (w["event_types"] or "").split(",") if x.strip()]
        if events and event_type not in events and "*" not in events:continue
        headers={"Content-Type":"application/json","User-Agent":"TVManager/6.0"}
        if w["secret"]:headers["X-TVManager-Secret"]=w["secret"]
        try:
            r=requests.post(w["url"],json={"event":event_type,"payload":payload},headers=headers,timeout=12)
            out.append({"name":w["name"],"ok":r.ok,"status":r.status_code})
        except Exception as e:out.append({"name":w["name"],"ok":False,"error":str(e)})
    import notifiers
    out.extend(notifiers.dispatch(event_type,payload))
    return out

def media_servers():
    with cx() as c:
        return [dict(r)|{"token":"••••••••" if r["token"] else "","password":"••••••••" if r["password"] else ""} for r in c.execute("SELECT * FROM media_servers ORDER BY name").fetchall()]

def media_server(sid, *, masked=True):
    with cx() as c:
        r=c.execute("SELECT * FROM media_servers WHERE id=?",(int(sid),)).fetchone()
    if not r:
        raise ValueError("Media server not found")
    d=dict(r)
    if masked:
        d["token"]="••••••••" if d.get("token") else ""
        d["password"]="••••••••" if d.get("password") else ""
    return d

def delete_media_server(sid):
    with cx() as c:
        cur=c.execute("DELETE FROM media_servers WHERE id=?",(int(sid),))
        c.commit()
    if cur.rowcount == 0:
        raise ValueError("Media server not found")
    return {"ok": True, "deleted": int(sid)}

def save_media_server(d):
    with cx() as c:
        if d.get("id"):
            old=c.execute("SELECT token,password FROM media_servers WHERE id=?",(d["id"],)).fetchone()
            tok=old["token"] if d.get("token")=="••••••••" and old else d.get("token","")
            pwd=old["password"] if d.get("password")=="••••••••" and old else d.get("password","")
            c.execute("""UPDATE media_servers SET name=?,kind=?,url=?,token=?,username=?,password=?,enabled=? WHERE id=?""",
                      (d["name"],d["kind"],d["url"],tok,d.get("username",""),pwd,1 if d.get("enabled",True) else 0,d["id"]))
            sid=d["id"]
        else:
            cur=c.execute("""INSERT INTO media_servers(name,kind,url,token,username,password,enabled) VALUES(?,?,?,?,?,?,?)""",
                          (d["name"],d["kind"],d["url"],d.get("token",""),d.get("username",""),d.get("password",""),1 if d.get("enabled",True) else 0))
            sid=cur.lastrowid
        c.commit();return sid

def test_media_server(sid):
    with cx() as c:s=c.execute("SELECT * FROM media_servers WHERE id=?",(sid,)).fetchone()
    if not s:raise ValueError("Media server not found")
    kind=s["kind"].lower();base=s["url"].rstrip("/")
    if kind=="plex":
        r=requests.get(base+"/identity",params={"X-Plex-Token":s["token"]},timeout=10);r.raise_for_status()
        return {"ok":True,"kind":"Plex","status":r.status_code}
    if kind in {"jellyfin","emby"}:
        headers={"X-Emby-Token":s["token"]} if s["token"] else {}
        r=requests.get(base+"/System/Info/Public",headers=headers,timeout=10);r.raise_for_status()
        return {"ok":True,"kind":s["kind"],"status":r.status_code}
    if kind=="kodi":
        payload={"jsonrpc":"2.0","method":"JSONRPC.Ping","id":1}
        auth=(s["username"],s["password"]) if s["username"] else None
        r=requests.post(base+"/jsonrpc",json=payload,auth=auth,timeout=10);r.raise_for_status()
        return {"ok":True,"kind":"Kodi","status":r.status_code}
    raise ValueError("Unsupported media server kind")

def _refresh_plex(server,target_path=None,tv_only=True):
    """Request scans using Plex's own paths; a foreign path needs a full TV scan."""
    import xml.etree.ElementTree as ET
    base=server['url'].rstrip('/')
    headers={'X-Plex-Token':server['token'],'Accept':'application/xml'}
    try:
        response=requests.get(base+'/library/sections',headers=headers,timeout=10)
        response.raise_for_status()
        root=ET.fromstring(response.content)
    except (requests.RequestException,ET.ParseError) as exc:
        raise ValueError('Plex library discovery failed; check connection and credentials') from None
    sections={}
    for directory in root.findall('.//Directory'):
        key=directory.get('key')
        if key and key.isdigit() and (not tv_only or directory.get('type')=='show'):
            sections.setdefault(key,[]).extend(loc.get('path') for loc in directory.findall('Location') if loc.get('path'))
    def normalized(path):
        path=str(path).replace('\\','/').rstrip('/')
        return path.casefold() if path.startswith('//') or re.match(r'^[A-Za-z]:',path) else path
    matches=[]
    if target_path:
        target=normalized(target_path)
        for key,locations in sections.items():
            for location in locations:
                rootpath=normalized(location)
                if target==rootpath or target.startswith(rootpath+'/'):
                    matches.append((len(rootpath),key))
    keys=sorted({key for length,key in matches if length==max(x[0] for x in matches)}) if matches else list(sections)
    if not keys:return {'ok':False,'kind':'plex','refreshed':0,'message':'No Plex TV libraries available' if tv_only else 'No Plex libraries available'}
    outcomes=[]
    for key in keys:
        params={'path':str(target_path)} if matches else {}
        try:
            response=requests.get(f'{base}/library/sections/{key}/refresh',headers=headers,params=params,timeout=10)
            response.raise_for_status()
            outcomes.append({'section':key,'ok':True})
        except requests.RequestException:
            outcomes.append({'section':key,'ok':False,'error':'Plex scan request failed; check connection and credentials'})
    ok=all(item['ok'] for item in outcomes)
    return {'ok':ok,'kind':'plex','targeted':bool(matches),'fallback':None if matches else ('tv_libraries' if tv_only else 'whole_library'),
            'path':str(target_path) if matches else None,'sections':outcomes,'refreshed':sum(item['ok'] for item in outcomes),
            'message':'Plex scan requested; indexing continues on Plex' if ok else 'One or more Plex scan requests failed'}


def refresh_media_server_target(sid,path=None,show_id=None):
    with cx() as c:
        server=c.execute("SELECT * FROM media_servers WHERE id=?",(sid,)).fetchone()
        show=c.execute("SELECT * FROM shows WHERE id=?",(show_id,)).fetchone() if show_id else None
    if not server:raise ValueError("Media server not found")
    target_path=path or (show["location"] if show else None)
    kind=(server["kind"] or "").lower();base=server["url"].rstrip("/")
    if kind=="plex":
        return _refresh_plex(server,target_path)
    # Jellyfin/Emby currently use their supported whole-library refresh as a safe fallback.
    result=refresh_media_server(sid)
    result["targeted"]=False
    result["fallback"]="whole_library"
    result["path"]=target_path
    return result


def refresh_media_server(sid):
    with cx() as c:s=c.execute("SELECT * FROM media_servers WHERE id=?",(sid,)).fetchone()
    if not s:raise ValueError("Media server not found")
    kind=s["kind"].lower();base=s["url"].rstrip("/")
    if kind=="plex":
        return _refresh_plex(s,tv_only=False)
    if kind in {"jellyfin","emby"}:
        headers={"X-Emby-Token":s["token"]} if s["token"] else {}
        r=requests.post(base+"/Library/Refresh",headers=headers,timeout=10);r.raise_for_status()
        return {"ok":True,"refreshed":1}
    if kind=="kodi":
        payload={"jsonrpc":"2.0","method":"VideoLibrary.Scan","id":1}
        auth=(s["username"],s["password"]) if s["username"] else None
        r=requests.post(base+"/jsonrpc",json=payload,auth=auth,timeout=10);r.raise_for_status()
        return {"ok":True,"refreshed":1}
    raise ValueError("Unsupported media server kind")
