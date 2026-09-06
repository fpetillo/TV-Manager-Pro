from __future__ import annotations
import dbcore
import lifecycle
import hashlib, secrets, sqlite3, json
from datetime import datetime
from pathlib import Path

BASE=Path(__file__).resolve().parent
DB=BASE/"tvmanager.db"

def cx():
    return dbcore.connect(DB)

def init():
    with cx() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS season_pack_downloads(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          show_id INTEGER NOT NULL,
          season INTEGER NOT NULL,
          search_id INTEGER,
          client TEXT,
          external_id TEXT,
          title TEXT,
          status TEXT DEFAULT 'Queued',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS api_access_log(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          token_id INTEGER,
          method TEXT,
          path TEXT,
          remote_addr TEXT,
          status INTEGER,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        c.commit()

def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_api_token(name):
    token=secrets.token_urlsafe(32)
    with cx() as c:
        c.execute("""INSERT INTO api_tokens(name,token_hash,enabled)
                     VALUES(?,?,1)
                     ON CONFLICT(name) DO UPDATE SET token_hash=excluded.token_hash,enabled=1,created_at=CURRENT_TIMESTAMP""",
                  (name,token_hash(token)))
        c.commit()
    return token

def verify_api_token(token):
    if not token:return None
    h=token_hash(token)
    with cx() as c:
        r=c.execute("SELECT id,name FROM api_tokens WHERE token_hash=? AND enabled=1",(h,)).fetchone()
        if r:c.execute("UPDATE api_tokens SET last_used=CURRENT_TIMESTAMP WHERE id=?",(r["id"],));c.commit()
    return dict(r) if r else None

def api_tokens():
    with cx() as c:
        return [dict(r) for r in c.execute("SELECT id,name,created_at,last_used,enabled FROM api_tokens ORDER BY name").fetchall()]

def revoke_api_token(tid):
    with cx() as c:c.execute("UPDATE api_tokens SET enabled=0 WHERE id=?",(tid,));c.commit()

def log_api_access(token_id,method,path,remote_addr,status):
    try:
        with cx() as c:
            c.execute("""INSERT INTO api_access_log(token_id,method,path,remote_addr,status)
                         VALUES(?,?,?,?,?)""",(token_id,method,path,remote_addr,int(status)))
            c.commit()
    except Exception:
        pass


def grab_season_pack(search_id):
    import engine
    with cx() as c:
        r=c.execute("""SELECT sp.*,s.name show_name FROM season_pack_searches sp
                       JOIN shows s ON s.id=sp.show_id WHERE sp.id=?""",(search_id,)).fetchone()
        if not r:raise ValueError("Season-pack search result not found")
        result=dict(r)
    protocol="torrent" if result.get("url","").startswith("magnet:") else None
    # Prefer saved provider protocol when known.
    with cx() as c:
        cp=c.execute("SELECT protocol FROM provider_definitions WHERE name=?",(result["provider"],)).fetchone()
    if cp: protocol="torrent" if cp["protocol"]=="torznab" else "nzb"
    if not protocol:
        protocol="nzb" if ".nzb" in (result.get("url") or "").lower() else "torrent"
    method=""
    client=""
    external=""
    if protocol=="nzb":
        method=(engine.get_setting("General","nzb_method","sabnzbd") or "sabnzbd").lower()
        if method=="sabnzbd":client="SABnzbd";external=engine.send_sab(result)
        elif method=="nzbget":client="NZBGet";external=engine.send_nzbget(result)
        else:raise ValueError(f"Unsupported NZB method for season pack: {method}")
    else:
        method=(engine.get_setting("General","torrent_method","qbittorrent") or "qbittorrent").lower()
        if method=="qbittorrent":client="qBittorrent";external=engine.send_qbit(result)
        elif method=="transmission":client="Transmission";external=engine.send_transmission(result)
        elif method=="deluge":client="Deluge";external=engine.send_deluge(result)
        else:raise ValueError(f"Unsupported torrent method for season pack: {method}")
    with cx() as c:
        cur=c.execute("""INSERT INTO season_pack_downloads(show_id,season,search_id,client,external_id,title,status,updated_at)
                         VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",(result["show_id"],result["season"],search_id,client,external,result["title"],"Queued"))
        lifecycle.transition("season_pack",cur.lastrowid,"Found","Queued",
                             message=f"Season pack queued in {client}",details={"search_id":search_id},conn=c)
        linked=c.execute("""SELECT id FROM episodes
                            WHERE show_id=? AND season=? AND (location IS NULL OR trim(location)='')
                            AND lower(COALESCE(status,'')) IN ('wanted','failed')""",
                         (result["show_id"],result["season"])).fetchall()
        for ep in linked:
            c.execute("""INSERT OR IGNORE INTO acquisition_episode_links(acquisition_type,acquisition_id,episode_id)
                         VALUES('season_pack',?,?)""",(cur.lastrowid,ep["id"]))
        c.execute("""UPDATE episodes SET status='Snatched',release_name=?
                     WHERE show_id=? AND season=? AND (location IS NULL OR trim(location)='')
                     AND lower(COALESCE(status,'')) IN ('wanted','failed')""",
                  (result["title"],result["show_id"],result["season"]))
        c.execute("UPDATE season_pack_searches SET status='Grabbed' WHERE id=?",(search_id,))
        c.commit()
    return {"ok":True,"client":client,"external_id":external,"season_pack_download_id":cur.lastrowid}

def mark_pack_processed(show_id,season):
    with cx() as c:
        packs=c.execute("""SELECT * FROM season_pack_downloads
                           WHERE show_id=? AND season=? AND status<>'Completed'""",(show_id,season)).fetchall()
        completed=0
        for pack in packs:
            linked=c.execute("""SELECT e.status,e.location FROM acquisition_episode_links l
                                JOIN episodes e ON e.id=l.episode_id
                                WHERE l.acquisition_type='season_pack' AND l.acquisition_id=?""",(pack["id"],)).fetchall()
            if linked and all(r["location"] and str(r["status"]).lower()=="downloaded" for r in linked):
                lifecycle.transition("season_pack",pack["id"],pack["status"],"Completed",
                                     message="All linked episodes imported",conn=c,force=True)
                c.execute("""UPDATE season_pack_downloads SET progress=1,
                             completed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?""",(pack["id"],))
                completed+=1
        c.commit()
    return completed
