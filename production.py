from __future__ import annotations
import dbcore
import hashlib, io, json, os, re, shutil, sqlite3, tempfile, zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
import requests

BASE=Path(__file__).resolve().parent
DB=BASE/"tvmanager.db"
DIAG=BASE/"diagnostics"
DIAG.mkdir(exist_ok=True)

def cx(path=None):
    return dbcore.connect(path or DB,wal=(path is None))

def init():
    with cx() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS subtitle_providers(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          kind TEXT NOT NULL DEFAULT 'opensubtitles',
          api_url TEXT NOT NULL DEFAULT 'https://api.opensubtitles.com/api/v1',
          api_key TEXT,
          username TEXT,
          password TEXT,
          token TEXT,
          languages TEXT DEFAULT 'en',
          enabled INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS subtitle_downloads(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          episode_id INTEGER,
          provider TEXT,
          language TEXT,
          destination TEXT,
          status TEXT,
          message TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS season_pack_searches(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          show_id INTEGER,
          season INTEGER,
          provider TEXT,
          title TEXT,
          url TEXT,
          guid TEXT,
          size INTEGER,
          seeders INTEGER,
          quality TEXT,
          score REAL,
          status TEXT DEFAULT 'Found',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS upgrade_candidates(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          episode_id INTEGER NOT NULL,
          current_quality TEXT,
          target_quality TEXT,
          reason TEXT,
          status TEXT DEFAULT 'Candidate',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sync_history(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source TEXT,
          matched INTEGER DEFAULT 0,
          updated INTEGER DEFAULT 0,
          errors INTEGER DEFAULT 0,
          detail_json TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        c.commit()

def _resolution(q):
    s=str(q or "").lower()
    if "2160" in s or "4k" in s:return 2160
    if "1080" in s:return 1080
    if "720" in s:return 720
    if "480" in s or "sd" in s:return 480
    return 0

def plan_upgrades():
    import engine
    with cx() as c:
        c.execute("DELETE FROM upgrade_candidates WHERE status='Candidate'")
        rows=c.execute("""SELECT e.id,e.quality,e.release_name,e.location,s.quality_profile_id
                          FROM episodes e JOIN shows s ON s.id=e.show_id
                          WHERE e.location IS NOT NULL AND trim(e.location)<>'' AND s.quality_profile_id IS NOT NULL""").fetchall()
        count=0
        for r in rows:
            p=c.execute("SELECT * FROM quality_profiles WHERE id=?",(r["quality_profile_id"],)).fetchone()
            if not p:continue
            current=_resolution(r["quality"])
            target=int(p["cutoff_resolution"] or p["max_resolution"] or 0)
            if p["upgrade_allowed"] and current and target and current<target:
                c.execute("""INSERT INTO upgrade_candidates(episode_id,current_quality,target_quality,reason)
                             VALUES(?,?,?,?)""",(r["id"],r["quality"],f"{target}p",f"Current resolution {current}p is below profile cutoff {target}p"))
                count+=1
        c.commit()
        rows=c.execute("""SELECT u.*,e.season,e.episode,e.show_id,s.name show_name
                          FROM upgrade_candidates u JOIN episodes e ON e.id=u.episode_id
                          JOIN shows s ON s.id=e.show_id WHERE u.status='Candidate'
                          ORDER BY s.name,e.season,e.episode""").fetchall()
    return {"count":count,"results":[dict(r) for r in rows]}

def subtitle_providers():
    with cx() as c:
        rows=c.execute("SELECT * FROM subtitle_providers ORDER BY name").fetchall()
    out=[]
    for r in rows:
        d=dict(r)
        for k in ("api_key","password","token"):
            if d.get(k):d[k]="••••••••"
        out.append(d)
    return out

def save_subtitle_provider(d):
    with cx() as c:
        if d.get("id"):
            old=c.execute("SELECT * FROM subtitle_providers WHERE id=?",(d["id"],)).fetchone()
            vals={}
            for k in ("api_key","password","token"):
                vals[k]=old[k] if d.get(k)=="••••••••" and old else d.get(k,"")
            c.execute("""UPDATE subtitle_providers SET name=?,kind=?,api_url=?,api_key=?,username=?,password=?,token=?,languages=?,enabled=? WHERE id=?""",
                      (d["name"],d.get("kind","opensubtitles"),d.get("api_url","https://api.opensubtitles.com/api/v1"),
                       vals["api_key"],d.get("username",""),vals["password"],vals["token"],d.get("languages","en"),
                       1 if d.get("enabled",True) else 0,d["id"]))
            pid=d["id"]
        else:
            cur=c.execute("""INSERT INTO subtitle_providers(name,kind,api_url,api_key,username,password,token,languages,enabled)
                             VALUES(?,?,?,?,?,?,?,?,?)""",
                          (d["name"],d.get("kind","opensubtitles"),d.get("api_url","https://api.opensubtitles.com/api/v1"),
                           d.get("api_key",""),d.get("username",""),d.get("password",""),d.get("token",""),
                           d.get("languages","en"),1 if d.get("enabled",True) else 0))
            pid=cur.lastrowid
        c.commit();return pid

def _opensub_headers(p):
    h={"Api-Key":p["api_key"],"User-Agent":"TVManager v10"}
    if p["token"]:h["Authorization"]="Bearer "+p["token"]
    return h

def search_subtitles(episode_id,language=None):
    with cx() as c:
        e=c.execute("""SELECT e.*,s.name show_name,s.imdb_id show_imdb FROM episodes e
                       JOIN shows s ON s.id=e.show_id WHERE e.id=?""",(episode_id,)).fetchone()
        providers=c.execute("SELECT * FROM subtitle_providers WHERE enabled=1").fetchall()
    if not e:raise ValueError("Episode not found")
    results=[];errors=[]
    for p in providers:
        if p["kind"].lower()!="opensubtitles":continue
        try:
            params={"query":e["show_name"],"season_number":e["season"],"episode_number":e["episode"],
                    "languages":language or p["languages"] or "en","type":"episode"}
            r=requests.get(p["api_url"].rstrip("/")+"/subtitles",params=params,headers=_opensub_headers(p),timeout=20)
            r.raise_for_status()
            for row in r.json().get("data",[]):
                attrs=row.get("attributes") or {}
                files=attrs.get("files") or []
                if not files:continue
                f=files[0]
                results.append({"provider":p["name"],"language":attrs.get("language"),"release":attrs.get("release"),
                                "file_id":f.get("file_id"),"file_name":f.get("file_name"),
                                "downloads":attrs.get("download_count"),"rating":attrs.get("ratings")})
        except Exception as ex:errors.append(f'{p["name"]}: {ex}')
    return {"episode_id":episode_id,"results":results,"errors":errors}

def download_subtitle(episode_id,provider_name,file_id,language="en"):
    with cx() as c:
        e=c.execute("SELECT * FROM episodes WHERE id=?",(episode_id,)).fetchone()
        p=c.execute("SELECT * FROM subtitle_providers WHERE name=? AND enabled=1",(provider_name,)).fetchone()
    if not e or not e["location"]:raise ValueError("Episode media file is not available")
    if not p:raise ValueError("Subtitle provider not found")
    media=Path(e["location"])
    if p["kind"].lower()=="opensubtitles":
        r=requests.post(p["api_url"].rstrip("/")+"/download",json={"file_id":int(file_id)},
                        headers=_opensub_headers(p),timeout=20);r.raise_for_status()
        link=r.json().get("link")
        if not link:raise ValueError("Subtitle provider did not return a download link")
        data=requests.get(link,timeout=30);data.raise_for_status()
        dest=media.with_name(media.stem+f".{language}.srt")
        dest.write_bytes(data.content)
    else:raise ValueError("Unsupported subtitle provider")
    with cx() as c:
        c.execute("""INSERT INTO subtitle_downloads(episode_id,provider,language,destination,status,message)
                     VALUES(?,?,?,?,?,?)""",(episode_id,provider_name,language,str(dest),"Downloaded","OK"))
        c.execute("UPDATE episodes SET subtitle_status='Present' WHERE id=?",(episode_id,));c.commit()
    try:
        import advanced
        advanced.fire_webhooks("subtitle",{"message":"Subtitle downloaded", "season":e["season"], "episode":e["episode"]})
    except Exception:pass
    return {"ok":True,"destination":str(dest)}

def validate_backup(path):
    p=Path(path)
    if not p.exists():raise ValueError("Backup not found")
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(p,"r") as z:
            bad=z.testzip()
            if bad:return {"ok":False,"error":f"Corrupt ZIP member: {bad}"}
            z.extractall(td)
        db=Path(td)/"tvmanager.db"
        if not db.exists():return {"ok":False,"error":"tvmanager.db missing from backup"}
        with cx(db) as c:
            result=c.execute("PRAGMA quick_check").fetchone()[0]
            tables=c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        return {"ok":result=="ok","quick_check":result,"tables":tables,"size":db.stat().st_size}

def diagnostic_bundle():
    stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
    out=DIAG/f"tvmanager-diagnostics-{stamp}.zip"
    import completion, ops
    health=completion.system_health()
    summary=ops.operations_summary()
    safe_settings=[]
    with cx() as c:
        for r in c.execute("SELECT section,name,value,is_secret,source FROM settings ORDER BY section,name").fetchall():
            d=dict(r)
            if d["is_secret"]:d["value"]="[REDACTED]"
            safe_settings.append(d)
        schema=[dict(r) for r in c.execute("SELECT type,name,sql FROM sqlite_master WHERE type IN ('table','index') ORDER BY type,name").fetchall()]
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("health.json",json.dumps(health,indent=2,default=str))
        z.writestr("operations.json",json.dumps(summary,indent=2,default=str))
        z.writestr("settings-redacted.json",json.dumps(safe_settings,indent=2,default=str))
        z.writestr("schema.json",json.dumps(schema,indent=2,default=str))
        z.writestr("version.txt",(BASE/"VERSION").read_text(encoding="utf-8") if (BASE/"VERSION").exists() else "unknown\n")
        logs=BASE/"logs"
        if logs.exists():
            for f in sorted(logs.glob("*"))[-20:]:
                if f.is_file() and f.stat().st_size<5_000_000:z.write(f,f"logs/{f.name}")
    return {"ok":True,"path":str(out),"filename":out.name}

def season_pack_search(show_id,season):
    import engine, advanced
    with cx() as c:
        show=c.execute("SELECT * FROM shows WHERE id=?",(show_id,)).fetchone()
    if not show:raise ValueError("Show not found")
    q=f'{show["name"]} S{season:02d}'
    providers=[p for p in engine.parse_newznab() if p["enabled"]]
    custom=advanced.provider_defs_raw()
    found=[];errors=[]
    # Reuse provider APIs but issue season query without episode.
    def parse_response(name,protocol,url,key,categories,min_seeders=0):
        params={"t":"tvsearch","q":q,"season":season,"extended":"1","o":"xml"}
        if key:params["apikey"]=key
        if categories:params["cat"]=categories
        r=requests.get(url.rstrip("/")+"/api",params=params,timeout=25,headers={"User-Agent":"TVManager/10.0"})
        r.raise_for_status()
        import xml.etree.ElementTree as ET
        root=ET.fromstring(r.content);items=[]
        for item in root.findall(".//item"):
            title=item.findtext("title") or "";link=item.findtext("link") or "";guid=item.findtext("guid") or link or title
            if not re.search(fr"(?i)\bS{season:02d}\b",title):continue
            if re.search(r"(?i)S\d{2}E\d{2}",title):continue
            enc=item.find("enclosure");size=0
            if enc is not None:
                link=enc.attrib.get("url") or link
                try:size=int(enc.attrib.get("length") or 0)
                except:size=0
            attrs={}
            for node in item.iter():
                if node.tag.endswith("attr") and node.attrib.get("name"):attrs[node.attrib["name"]]=node.attrib.get("value")
            try:seeders=int(attrs.get("seeders") or 0)
            except:seeders=0
            if seeders<int(min_seeders or 0):continue
            score,reject=engine.score_release(title,dict(show))
            if reject:continue
            items.append({"provider":name,"protocol":protocol,"title":title,"url":link,"guid":guid,"size":size,
                          "seeders":seeders,"quality":engine.infer_quality(title),"score":score})
        return items
    for p in providers:
        try:found+=parse_response(p["name"],"nzb",p["url"],p.get("api_key"),p.get("categories"))
        except Exception as e:errors.append(f'{p["name"]}: {e}')
    for p in custom:
        try:found+=parse_response(p["name"],"torrent" if p["protocol"]=="torznab" else "nzb",p["url"],p.get("api_key"),p.get("categories"),p.get("minimum_seeders"))
        except Exception as e:errors.append(f'{p["name"]}: {e}')
    found.sort(key=lambda x:(-x["score"],-(x["seeders"] or 0),-(x["size"] or 0)))
    with cx() as c:
        c.execute("DELETE FROM season_pack_searches WHERE show_id=? AND season=?",(show_id,season))
        for x in found:
            cur=c.execute("""INSERT INTO season_pack_searches(show_id,season,provider,title,url,guid,size,seeders,quality,score)
                             VALUES(?,?,?,?,?,?,?,?,?,?)""",(show_id,season,x["provider"],x["title"],x["url"],x["guid"],x["size"],x["seeders"],x["quality"],x["score"]))
            x["id"]=cur.lastrowid
        c.commit()
    return {"show":show["name"],"season":season,"results":found,"errors":errors}
