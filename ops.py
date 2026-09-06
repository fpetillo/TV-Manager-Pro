from __future__ import annotations
import dbcore
import json, os, sqlite3, hashlib, shutil
from datetime import datetime, timedelta
from pathlib import Path

BASE=Path(__file__).resolve().parent
DB=BASE/"tvmanager.db"

def cx():
    return dbcore.connect(DB)

def now():
    return datetime.now().replace(microsecond=0).isoformat()

def init():
    with cx() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS provider_health(
          provider TEXT PRIMARY KEY,
          success_count INTEGER DEFAULT 0,
          failure_count INTEGER DEFAULT 0,
          consecutive_failures INTEGER DEFAULT 0,
          avg_latency_ms REAL DEFAULT 0,
          last_latency_ms REAL,
          last_success TEXT,
          last_failure TEXT,
          last_error TEXT,
          suspended_until TEXT
        );
        CREATE TABLE IF NOT EXISTS search_decisions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          episode_id INTEGER,
          search_result_id INTEGER,
          provider TEXT,
          title TEXT,
          accepted INTEGER DEFAULT 0,
          score REAL,
          reasons_json TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_search_decision_episode ON search_decisions(episode_id);

        CREATE TABLE IF NOT EXISTS automation_rules(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          enabled INTEGER DEFAULT 1,
          priority INTEGER DEFAULT 100,
          event_type TEXT NOT NULL DEFAULT 'search_result',
          field TEXT,
          operator TEXT,
          value TEXT,
          action TEXT NOT NULL DEFAULT 'score',
          action_value TEXT,
          stop_processing INTEGER DEFAULT 0,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS config_snapshots(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          data_json TEXT NOT NULL,
          checksum TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS path_mappings(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          remote_path TEXT NOT NULL,
          local_path TEXT NOT NULL,
          enabled INTEGER DEFAULT 1,
          UNIQUE(remote_path,local_path)
        );

        CREATE TABLE IF NOT EXISTS library_conflicts(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          kind TEXT NOT NULL,
          show_id INTEGER,
          episode_id INTEGER,
          path1 TEXT,
          path2 TEXT,
          message TEXT,
          resolved INTEGER DEFAULT 0,
          detected_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS operation_runs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          operation TEXT NOT NULL,
          status TEXT,
          summary_json TEXT,
          started_at TEXT DEFAULT CURRENT_TIMESTAMP,
          completed_at TEXT
        );
        """)
        # Sensible starter rules: visible, editable, not magical.
        defaults=[
          ("Prefer REPACK",1,20,"search_result","title","contains","repack","score","8",0),
          ("Prefer PROPER",1,30,"search_result","title","contains","proper","score","6",0),
          ("Reject CAM",1,1,"search_result","title","contains","cam","reject","CAM release",1),
          ("Reject telesync",1,2,"search_result","title","contains","telesync","reject","Telesync release",1),
        ]
        for r in defaults:
            c.execute("""INSERT INTO automation_rules(name,enabled,priority,event_type,field,operator,value,action,action_value,stop_processing)
                         SELECT ?,?,?,?,?,?,?,?,?,?
                         WHERE NOT EXISTS(SELECT 1 FROM automation_rules WHERE name=?)""",r+(r[0],))
        c.commit()

def provider_is_available(name):
    with cx() as c:r=c.execute("SELECT suspended_until FROM provider_health WHERE provider=?",(name,)).fetchone()
    if not r or not r["suspended_until"]:return True
    try:return datetime.now()>=datetime.fromisoformat(r["suspended_until"])
    except Exception:return True

def provider_result(name, ok, latency_ms=None, error=None):
    with cx() as c:
        r=c.execute("SELECT * FROM provider_health WHERE provider=?",(name,)).fetchone()
        if not r:
            c.execute("INSERT INTO provider_health(provider) VALUES(?)",(name,))
            r=c.execute("SELECT * FROM provider_health WHERE provider=?",(name,)).fetchone()
        successes=r["success_count"];fails=r["failure_count"];consecutive=r["consecutive_failures"]
        avg=r["avg_latency_ms"] or 0
        if ok:
            successes+=1;consecutive=0
            if latency_ms is not None:
                avg=((avg*(successes-1))+latency_ms)/successes
            c.execute("""UPDATE provider_health SET success_count=?,consecutive_failures=0,avg_latency_ms=?,
                         last_latency_ms=?,last_success=?,last_error=NULL,suspended_until=NULL WHERE provider=?""",
                      (successes,avg,latency_ms,now(),name))
        else:
            fails+=1;consecutive+=1
            cooldown=min(360, 5*(2**max(0,consecutive-1)))
            suspended=(datetime.now()+timedelta(minutes=cooldown)).replace(microsecond=0).isoformat() if consecutive>=3 else None
            c.execute("""UPDATE provider_health SET failure_count=?,consecutive_failures=?,last_failure=?,
                         last_error=?,suspended_until=COALESCE(?,suspended_until) WHERE provider=?""",
                      (fails,consecutive,now(),str(error or "")[:1000],suspended,name))
        c.commit()

def provider_health():
    with cx() as c:
        rows=c.execute("SELECT * FROM provider_health ORDER BY consecutive_failures DESC,failure_count DESC,provider").fetchall()
    out=[]
    for r in rows:
        d=dict(r);total=d["success_count"]+d["failure_count"]
        d["success_rate"]=round((d["success_count"]/total*100),1) if total else None
        d["available"]=provider_is_available(d["provider"])
        out.append(d)
    return out

def active_rules(event_type="search_result"):
    with cx() as c:return [dict(r) for r in c.execute("SELECT * FROM automation_rules WHERE enabled=1 AND event_type=? ORDER BY priority,id",(event_type,)).fetchall()]

def _match(field_value,operator,target):
    fv="" if field_value is None else str(field_value)
    tv="" if target is None else str(target)
    op=(operator or "").lower()
    if op=="contains":return tv.lower() in fv.lower()
    if op=="not_contains":return tv.lower() not in fv.lower()
    if op=="equals":return fv.lower()==tv.lower()
    if op=="regex":
        import re
        try:return bool(re.search(tv,fv,re.I))
        except Exception:return False
    if op in {"gt","gte","lt","lte"}:
        try:a=float(fv);b=float(tv)
        except Exception:return False
        return {"gt":a>b,"gte":a>=b,"lt":a<b,"lte":a<=b}[op]
    return False

def apply_rules(item):
    score=float(item.get("score") or 0);rejected=item.get("rejected_reason")
    reasons=list(item.get("decision_reasons") or [])
    for rule in active_rules():
        val=item.get(rule["field"])
        if not _match(val,rule["operator"],rule["value"]):continue
        act=rule["action"]
        if act=="score":
            delta=float(rule["action_value"] or 0);score+=delta
            reasons.append(f'Rule "{rule["name"]}": score {delta:+g}')
        elif act=="reject":
            rejected=rule["action_value"] or f'Rejected by rule {rule["name"]}'
            reasons.append(f'Rule "{rule["name"]}": rejected')
        elif act=="accept":
            if rejected:
                reasons.append(f'Rule "{rule["name"]}": accept ignored because a rejection is already active')
            else:
                reasons.append(f'Rule "{rule["name"]}": accepted')
        if rule["stop_processing"]:break
    item["score"]=score;item["rejected_reason"]=rejected;item["decision_reasons"]=reasons
    return item

def record_decision(episode_id,result_id,item,conn=None):
    reasons=list(item.get("decision_reasons") or [])
    if item.get("rejected_reason"):reasons.append(item["rejected_reason"])
    owns=conn is None
    c=conn or cx()
    try:
        c.execute("""INSERT INTO search_decisions(episode_id,search_result_id,provider,title,accepted,score,reasons_json)
                     VALUES(?,?,?,?,?,?,?)""",(episode_id,result_id,item.get("provider"),item.get("title"),
                         0 if item.get("rejected_reason") else 1,item.get("score"),json.dumps(reasons)))
        if owns:c.commit()
    finally:
        if owns:c.close()

def decisions(episode_id,limit=200):
    with cx() as c:rows=c.execute("SELECT * FROM search_decisions WHERE episode_id=? ORDER BY id DESC LIMIT ?",(episode_id,limit)).fetchall()
    out=[]
    for r in rows:
        d=dict(r)
        try:d["reasons"]=json.loads(d.pop("reasons_json") or "[]")
        except Exception:d["reasons"]=[]
        out.append(d)
    return out

def rules():
    with cx() as c:return [dict(r) for r in c.execute("SELECT * FROM automation_rules ORDER BY priority,id").fetchall()]

def save_rule(d):
    with cx() as c:
        if d.get("id"):
            c.execute("""UPDATE automation_rules SET name=?,enabled=?,priority=?,event_type=?,field=?,operator=?,value=?,
                         action=?,action_value=?,stop_processing=? WHERE id=?""",
                      (d["name"],1 if d.get("enabled",True) else 0,int(d.get("priority",100)),d.get("event_type","search_result"),
                       d.get("field","title"),d.get("operator","contains"),d.get("value",""),d.get("action","score"),
                       d.get("action_value",""),1 if d.get("stop_processing",False) else 0,d["id"]))
            rid=d["id"]
        else:
            cur=c.execute("""INSERT INTO automation_rules(name,enabled,priority,event_type,field,operator,value,action,action_value,stop_processing)
                             VALUES(?,?,?,?,?,?,?,?,?,?)""",
                          (d["name"],1 if d.get("enabled",True) else 0,int(d.get("priority",100)),d.get("event_type","search_result"),
                           d.get("field","title"),d.get("operator","contains"),d.get("value",""),d.get("action","score"),
                           d.get("action_value",""),1 if d.get("stop_processing",False) else 0))
            rid=cur.lastrowid
        c.commit();return rid

def delete_rule(rid):
    with cx() as c:c.execute("DELETE FROM automation_rules WHERE id=?",(rid,));c.commit()

def _snapshot_payload():
    tables=["settings","quality_profiles","scheduler_jobs","provider_definitions","webhooks","media_servers","automation_rules","path_mappings"]
    payload={}
    with cx() as c:
        for t in tables:
            exists=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone()
            if exists:payload[t]=[dict(r) for r in c.execute(f'SELECT * FROM "{t}"').fetchall()]
    return payload

def create_snapshot(name):
    data=_snapshot_payload();raw=json.dumps(data,sort_keys=True,default=str)
    checksum=hashlib.sha256(raw.encode()).hexdigest()
    with cx() as c:
        cur=c.execute("INSERT INTO config_snapshots(name,data_json,checksum) VALUES(?,?,?)",(name,raw,checksum));c.commit()
    return {"id":cur.lastrowid,"name":name,"checksum":checksum}

def snapshots():
    with cx() as c:return [dict(r) for r in c.execute("SELECT id,name,checksum,created_at FROM config_snapshots ORDER BY id DESC").fetchall()]

def restore_snapshot(sid):
    with cx() as c:
        snap=c.execute("SELECT * FROM config_snapshots WHERE id=?",(sid,)).fetchone()
        if not snap:raise ValueError("Snapshot not found")
        data=json.loads(snap["data_json"])
        c.execute("BEGIN")
        try:
            for t,rows in data.items():
                exists=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone()
                if not exists:continue
                c.execute(f'DELETE FROM "{t}"')
                for row in rows:
                    cols=list(row);qs=",".join("?" for _ in cols)
                    c.execute(f'INSERT INTO "{t}" ({",".join(cols)}) VALUES({qs})',[row[k] for k in cols])
            c.commit()
        except Exception:
            c.rollback();raise
    return {"ok":True,"name":snap["name"]}

def path_mappings():
    with cx() as c:return [dict(r) for r in c.execute("SELECT * FROM path_mappings ORDER BY name,id").fetchall()]

def save_path_mapping(d):
    with cx() as c:
        if d.get("id"):
            c.execute("UPDATE path_mappings SET name=?,remote_path=?,local_path=?,enabled=? WHERE id=?",
                      (d["name"],d["remote_path"],d["local_path"],1 if d.get("enabled",True) else 0,d["id"]))
            mid=d["id"]
        else:
            cur=c.execute("INSERT INTO path_mappings(name,remote_path,local_path,enabled) VALUES(?,?,?,?)",
                          (d["name"],d["remote_path"],d["local_path"],1 if d.get("enabled",True) else 0));mid=cur.lastrowid
        c.commit();return mid

def map_path(path):
    p=str(path or "")
    for m in path_mappings():
        if m["enabled"] and p.lower().startswith(m["remote_path"].lower()):
            return m["local_path"]+p[len(m["remote_path"]):]
    return p

def root_health():
    with cx() as c:rows=c.execute("""SELECT id,name,location FROM shows WHERE location IS NOT NULL AND trim(location)<>'' ORDER BY name""").fetchall()
    items=[];reachable=missing=0
    for r in rows:
        mapped=map_path(r["location"]);p=Path(mapped)
        ok=p.exists()
        writable=False
        if ok:
            reachable+=1
            try:writable=os.access(p,os.W_OK)
            except Exception:writable=False
        else:missing+=1
        items.append({"show_id":r["id"],"show":r["name"],"configured":r["location"],"mapped":mapped,"reachable":ok,"writable":writable})
    return {"checked":len(items),"reachable":reachable,"missing":missing,"items":items[:1000]}

def detect_conflicts():
    with cx() as c:
        c.execute("DELETE FROM library_conflicts WHERE resolved=0")
        rows=c.execute("""SELECT e.id episode_id,e.show_id,e.season,e.episode,e.location,s.name show_name
                          FROM episodes e JOIN shows s ON s.id=e.show_id
                          WHERE e.location IS NOT NULL AND trim(e.location)<>''""").fetchall()
        by_path={}
        conflicts=[]
        for r in rows:
            mapped=map_path(r["location"]);key=os.path.normcase(os.path.normpath(mapped))
            if key in by_path:
                prev=by_path[key]
                msg=f'Same media path assigned to {prev["show_name"]} S{prev["season"]:02d}E{prev["episode"]:02d} and {r["show_name"]} S{r["season"]:02d}E{r["episode"]:02d}'
                c.execute("""INSERT INTO library_conflicts(kind,show_id,episode_id,path1,path2,message)
                             VALUES('duplicate_path',?,?,?,?,?)""",(r["show_id"],r["episode_id"],prev["location"],r["location"],msg))
                conflicts.append(msg)
            else:by_path[key]=dict(r)
        # Same logical episode with multiple distinct records/files.
        dupes=c.execute("""SELECT show_id,season,episode,COUNT(*) c FROM episodes
                           WHERE location IS NOT NULL AND trim(location)<>'' GROUP BY show_id,season,episode HAVING COUNT(*)>1""").fetchall()
        for d in dupes:
            rs=c.execute("SELECT id,location FROM episodes WHERE show_id=? AND season=? AND episode=? AND location IS NOT NULL",
                         (d["show_id"],d["season"],d["episode"])).fetchall()
            if len({os.path.normcase(os.path.normpath(map_path(x["location"]))) for x in rs})>1:
                show=c.execute("SELECT name FROM shows WHERE id=?",(d["show_id"],)).fetchone()
                msg=f'{show["name"]} S{d["season"]:02d}E{d["episode"]:02d} has multiple media paths'
                c.execute("""INSERT INTO library_conflicts(kind,show_id,episode_id,path1,path2,message)
                             VALUES('multiple_files',?,?,?,?,?)""",(d["show_id"],rs[0]["id"],rs[0]["location"],rs[1]["location"],msg))
                conflicts.append(msg)
        c.commit()
        rows=c.execute("SELECT * FROM library_conflicts WHERE resolved=0 ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]

def operations_summary():
    rh=root_health()
    return {"provider_health":provider_health(),"root_health":{"checked":rh["checked"],"reachable":rh["reachable"],"missing":rh["missing"]},
            "rules":len(rules()),"snapshots":len(snapshots()),"conflicts":len(detect_conflicts()),"path_mappings":len(path_mappings())}
