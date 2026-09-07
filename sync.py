from __future__ import annotations
import dbcore
import json, sqlite3
from pathlib import Path
import requests

BASE=Path(__file__).resolve().parent
DB=BASE/"tvmanager.db"

def cx():
    return dbcore.connect(DB)

def init():
    with cx() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS mapping_sources(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          kind TEXT NOT NULL,
          base_url TEXT,
          enabled INTEGER DEFAULT 1,
          last_sync TEXT,
          last_error TEXT
        );
        CREATE TABLE IF NOT EXISTS subtitle_jobs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          episode_id INTEGER NOT NULL,
          language TEXT DEFAULT 'en',
          status TEXT DEFAULT 'Pending',
          attempts INTEGER DEFAULT 0,
          last_error TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(episode_id,language)
        );
        CREATE TABLE IF NOT EXISTS watched_sync_profiles(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          media_server_id INTEGER NOT NULL,
          profile_name TEXT NOT NULL DEFAULT 'default',
          external_user_id TEXT,
          enabled INTEGER DEFAULT 1,
          last_sync TEXT,
          UNIQUE(media_server_id,profile_name)
        );
        CREATE TABLE IF NOT EXISTS proper_upgrade_runs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          searched INTEGER DEFAULT 0,
          candidates INTEGER DEFAULT 0,
          grabbed INTEGER DEFAULT 0,
          details_json TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        c.commit()

def _episode_lookup_by_path(path):
    if not path:return None
    p=str(path).replace("\\","/").lower()
    with cx() as c:
        rows=c.execute("""SELECT e.id,e.show_id,e.season,e.episode,e.location,s.name show_name
                          FROM episodes e JOIN shows s ON s.id=e.show_id
                          WHERE e.location IS NOT NULL AND trim(e.location)<>''""").fetchall()
    for r in rows:
        loc=str(r["location"] or "").replace("\\","/").lower()
        if loc==p or (loc and p.endswith(Path(loc).name.lower())):
            return dict(r)
    return None

def _episode_lookup(show_name,season,episode):
    with cx() as c:
        r=c.execute("""SELECT e.id,e.show_id,e.season,e.episode,s.name show_name
                       FROM episodes e JOIN shows s ON s.id=e.show_id
                       WHERE lower(s.name)=lower(?) AND e.season=? AND e.episode=? LIMIT 1""",
                    (show_name,int(season),int(episode))).fetchone()
    return dict(r) if r else None

def sync_jellyfin(server_id, profile="default", user_id=None):
    import completion
    with cx() as c:s=c.execute("SELECT * FROM media_servers WHERE id=?",(server_id,)).fetchone()
    if not s:raise ValueError("Media server not found")
    raw=dict(s);base=raw["url"].rstrip("/");token=raw.get("token") or raw.get("api_key") or ""
    headers={"X-Emby-Token":token}
    if not user_id:
        r=requests.get(base+"/Users",headers=headers,timeout=20);r.raise_for_status()
        users=r.json()
        if not users:raise ValueError("No Jellyfin/Emby users returned")
        user_id=users[0]["Id"]
    params={"Recursive":"true","IncludeItemTypes":"Episode","Fields":"Path","EnableUserData":"true","Limit":10000}
    r=requests.get(f"{base}/Users/{user_id}/Items",headers=headers,params=params,timeout=45);r.raise_for_status()
    matched=updated=errors=0
    for item in r.json().get("Items",[]):
        try:
            ep=_episode_lookup_by_path(item.get("Path"))
            if not ep and item.get("SeriesName") is not None and item.get("ParentIndexNumber") is not None and item.get("IndexNumber") is not None:
                ep=_episode_lookup(item["SeriesName"],item["ParentIndexNumber"],item["IndexNumber"])
            if not ep:continue
            matched+=1
            ud=item.get("UserData") or {}
            pct=ud.get("PlayedPercentage")
            if pct is None:pct=100 if ud.get("Played") else 0
            completion.set_watched(ep["id"],pct,profile,(raw.get("kind") or "jellyfin").lower())
            updated+=1
        except Exception:errors+=1
    with cx() as c:
        c.execute("INSERT INTO sync_history(source,matched,updated,errors,detail_json) VALUES(?,?,?,?,?)",
                  ("jellyfin",matched,updated,errors,json.dumps({"server_id":server_id,"user_id":user_id})))
        c.execute("""INSERT INTO watched_sync_profiles(media_server_id,profile_name,external_user_id,enabled,last_sync)
                     VALUES(?,?,?,?,CURRENT_TIMESTAMP)
                     ON CONFLICT(media_server_id,profile_name) DO UPDATE SET external_user_id=excluded.external_user_id,last_sync=CURRENT_TIMESTAMP""",
                  (server_id,profile,user_id,1));c.commit()
    return {"source":"jellyfin","matched":matched,"updated":updated,"errors":errors,"user_id":user_id}

def sync_plex(server_id,profile="default"):
    import completion
    with cx() as c:s=c.execute("SELECT * FROM media_servers WHERE id=?",(server_id,)).fetchone()
    if not s:raise ValueError("Media server not found")
    raw=dict(s);base=raw["url"].rstrip("/");token=raw.get("token") or ""
    headers={"X-Plex-Token":token,"Accept":"application/json"}
    sr=requests.get(base+"/library/sections",headers=headers,timeout=20);sr.raise_for_status()
    sections=sr.json().get("MediaContainer",{}).get("Directory",[])
    items=[]
    for sec in sections:
        if sec.get("type")!="show":continue
        rr=requests.get(f'{base}/library/sections/{sec["key"]}/all',headers=headers,params={"type":4},timeout=30)
        if rr.ok:items+=rr.json().get("MediaContainer",{}).get("Metadata",[])
    matched=updated=errors=0
    for item in items:
        try:
            ep=_episode_lookup(item.get("grandparentTitle",""),item.get("parentIndex"),item.get("index"))
            if not ep:continue
            matched+=1
            vc=int(item.get("viewCount") or 0);off=int(item.get("viewOffset") or 0);dur=int(item.get("duration") or 0)
            pct=100.0 if vc>0 and off==0 else ((off/dur)*100.0 if dur else (100.0 if vc>0 else 0.0))
            completion.set_watched(ep["id"],pct,profile,"plex");updated+=1
        except Exception:errors+=1
    with cx() as c:
        c.execute("INSERT INTO sync_history(source,matched,updated,errors,detail_json) VALUES(?,?,?,?,?)",
                  ("plex",matched,updated,errors,json.dumps({"server_id":server_id})));c.commit()
    return {"source":"plex","matched":matched,"updated":updated,"errors":errors}

def sync_watched(server_id,profile="default",user_id=None):
    with cx() as c:s=c.execute("SELECT kind FROM media_servers WHERE id=?",(server_id,)).fetchone()
    if not s:raise ValueError("Media server not found")
    kind=(s["kind"] or "").lower()
    if kind in {"jellyfin","emby"}:return sync_jellyfin(server_id,profile,user_id)
    if kind=="plex":return sync_plex(server_id,profile)
    raise ValueError(f"Watched-state sync not implemented for {kind}")


def preferred_subtitle_languages():
    # Preserve imported SickChill preferences where available.
    keys=("subtitles_languages","subtitles_language","languages","language")
    with cx() as c:
        vals=[]
        for key in keys:
            r=c.execute("""SELECT value FROM settings WHERE lower(section)='subtitles' AND lower(name)=?""",(key,)).fetchone()
            if r and r["value"]: vals.append(str(r["value"]))
        if not vals:
            r=c.execute("""SELECT languages FROM subtitle_providers WHERE enabled=1 AND languages IS NOT NULL
                           AND trim(languages)<>'' ORDER BY id LIMIT 1""").fetchone()
            if r:vals.append(r["languages"])
    raw=vals[0] if vals else "en"
    langs=[]
    for x in re.split(r"[,|;\s]+",raw):
        x=x.strip().lower()
        if x and x not in langs:langs.append(x)
    return langs or ["en"]

def enqueue_preferred_subtitles():
    counts={}
    for lang in preferred_subtitle_languages():
        counts[lang]=enqueue_missing_subtitles(lang)
    return counts

def enqueue_missing_subtitles(language="en"):
    with cx() as c:
        rows=c.execute("""SELECT e.id FROM episodes e JOIN shows s ON s.id=e.show_id WHERE COALESCE(s.subtitles_enabled,1)=1 AND e.location IS NOT NULL AND trim(e.location)<>''
                          AND lower(COALESCE(e.subtitle_status,''))<>'present'""").fetchall()
        created=0
        for r in rows:
            cur=c.execute("""INSERT INTO subtitle_jobs(episode_id,language,status) VALUES(?,?,'Pending')
                             ON CONFLICT(episode_id,language) DO NOTHING""",(r["id"],language))
            created+=max(0,cur.rowcount)
        c.commit()
    return created

def run_subtitle_jobs(limit=20):
    import production
    with cx() as c:
        jobs=c.execute("""SELECT * FROM subtitle_jobs WHERE status IN ('Pending','Failed')
                          AND attempts<5
                          AND (next_attempt_at IS NULL OR next_attempt_at<=CURRENT_TIMESTAMP)
                          ORDER BY priority DESC,id LIMIT ?""",(int(limit),)).fetchall()
    done=failed=0
    for j in jobs:
        try:
            res=production.search_subtitles(j["episode_id"],language=j["language"])
            matches=[x for x in res["results"] if not j["language"] or str(x.get("language") or "").lower()==str(j["language"]).lower()]
            if not matches:matches=res["results"]
            if not matches:raise ValueError("No subtitle results")
            best=matches[0]
            production.download_subtitle(j["episode_id"],best["provider"],best["file_id"],best.get("language") or j["language"])
            with cx() as c:
                c.execute("""UPDATE subtitle_jobs SET status='Completed',attempts=attempts+1,last_error=NULL,
                             provider=?,next_attempt_at=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?""",(best["provider"],j["id"]))
                c.commit()
            done+=1
        except Exception as e:
            delay=min(1440,15*(2**int(j["attempts"] or 0)))
            with cx() as c:
                c.execute("""UPDATE subtitle_jobs SET status='Failed',attempts=attempts+1,last_error=?,
                             next_attempt_at=datetime(CURRENT_TIMESTAMP, ?),updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                          (str(e)[:1000],f"+{delay} minutes",j["id"]))
                c.commit()
            failed+=1
    return {"completed":done,"failed":failed}

def proper_repack_candidates(limit=50):
    with cx() as c:
        rows=c.execute("""SELECT e.id,e.release_name,e.season,e.episode,s.name show_name
                          FROM episodes e JOIN shows s ON s.id=e.show_id
                          WHERE e.location IS NOT NULL AND trim(e.location)<>'' AND lower(COALESCE(e.status,''))='downloaded'
                          ORDER BY COALESCE(e.airdate,'') DESC LIMIT ?""",(int(limit),)).fetchall()
    out=[]
    for r in rows:
        title=(r["release_name"] or "").upper()
        if "REPACK" in title or "PROPER" in title:continue
        out.append({"episode_id":r["id"],"show":r["show_name"],"season":r["season"],"episode":r["episode"],
                    "current_release":r["release_name"],"reason":"Downloaded release has no PROPER/REPACK marker"})
    return out

def mapping_status():
    with cx() as c:return [dict(r) for r in c.execute("SELECT * FROM mapping_sources ORDER BY name").fetchall()]

def save_mapping_source(name,kind,base_url,enabled=True):
    with cx() as c:
        c.execute("""INSERT INTO mapping_sources(name,kind,base_url,enabled) VALUES(?,?,?,?)
                     ON CONFLICT(name) DO UPDATE SET kind=excluded.kind,base_url=excluded.base_url,enabled=excluded.enabled""",
                  (name,kind,base_url,1 if enabled else 0));c.commit()


def proper_repack_search(episode_id, grab=False):
    import engine
    result=engine.search_episode(int(episode_id),auto_grab=False)
    candidates=[]
    for row in result.get("results") or []:
        title=str(row.get("title") or "")
        if row.get("rejected_reason"):continue
        if "proper" not in title.lower() and "repack" not in title.lower():continue
        candidates.append(row)
    candidates.sort(key=lambda x:float(x.get("score") or 0),reverse=True)
    grabbed=None
    if grab and candidates:
        if engine.as_bool(engine.get_setting("TVManager","simulation_mode","0")):
            raise ValueError("Simulation mode is enabled; Proper/Repack grab was blocked")
        grabbed=engine.grab_result(candidates[0]["id"])
    with cx() as c:
        c.execute("""INSERT INTO proper_upgrade_runs(searched,candidates,grabbed,details_json)
                     VALUES(?,?,?,?)""",(1,len(candidates),1 if grabbed else 0,
                       json.dumps({"episode_id":episode_id,"best":candidates[0]["title"] if candidates else None})))
        c.commit()
    return {"episode_id":episode_id,"candidates":candidates,"grabbed":grabbed}
