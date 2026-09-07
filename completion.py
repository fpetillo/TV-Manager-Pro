from __future__ import annotations
import dbcore
import json, os, sqlite3, shutil, hashlib
from datetime import datetime, date, timedelta
from pathlib import Path

BASE=Path(__file__).resolve().parent
DB=BASE/"tvmanager.db"
TRASH=BASE/"managed_trash"
TRASH.mkdir(exist_ok=True)

def cx():
    return dbcore.connect(DB)

def init():
    with cx() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS retention_runs(
          id INTEGER PRIMARY KEY AUTOINCREMENT, policy_id INTEGER, dry_run INTEGER DEFAULT 1,
          candidates INTEGER DEFAULT 0, bytes_reclaimable INTEGER DEFAULT 0, deleted INTEGER DEFAULT 0,
          details_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS api_tokens(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, token_hash TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP, last_used TEXT, enabled INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS system_checks(
          id INTEGER PRIMARY KEY AUTOINCREMENT, check_name TEXT, status TEXT, detail TEXT,
          checked_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS watched_state(
          episode_id INTEGER NOT NULL, profile TEXT NOT NULL DEFAULT 'default',
          played_percent REAL DEFAULT 0, watched_at TEXT, source TEXT,
          PRIMARY KEY(episode_id,profile)
        );
        CREATE TABLE IF NOT EXISTS upgrade_history(
          id INTEGER PRIMARY KEY AUTOINCREMENT, episode_id INTEGER, old_quality TEXT, new_quality TEXT,
          release_name TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        c.commit()

def retention_preview(policy_id):
    with cx() as c:
        p=c.execute("SELECT * FROM retention_policies WHERE id=?",(policy_id,)).fetchone()
        if not p: raise ValueError("Retention policy not found")
        shows=c.execute("SELECT id,name FROM shows WHERE retention_policy_id=?",(policy_id,)).fetchall()
        candidates=[]
        cutoff=(date.today()-timedelta(days=int(p["keep_days"]))).isoformat() if p["keep_days"] else None
        for s in shows:
            rows=c.execute("""SELECT e.*,COALESCE(w.played_percent,0) played_percent
                              FROM episodes e LEFT JOIN watched_state w ON w.episode_id=e.id AND w.profile='default'
                              WHERE e.show_id=? AND e.location IS NOT NULL AND trim(e.location)<>''
                              ORDER BY COALESCE(e.airdate,'9999-12-31') DESC,e.season DESC,e.episode DESC""",(s["id"],)).fetchall()
            keep_latest=int(p["keep_latest"] or 0)
            for idx,e in enumerate(rows):
                reasons=[]
                if keep_latest and idx < keep_latest: continue
                if cutoff and e["airdate"] and e["airdate"] >= cutoff: continue
                if p["keep_watched"] and float(e["played_percent"] or 0)>=90: continue
                lock=c.execute("SELECT 1 FROM episode_locks WHERE episode_id=? AND locked=1",(e["id"],)).fetchone()
                if lock: continue
                path=Path(e["location"]);size=path.stat().st_size if path.exists() and path.is_file() else int(e["file_size"] or 0)
                if keep_latest: reasons.append(f"outside latest {keep_latest}")
                if cutoff: reasons.append(f"older than {p['keep_days']} days")
                candidates.append({"episode_id":e["id"],"show":s["name"],"season":e["season"],"episode":e["episode"],
                                   "path":e["location"],"size":size,"reason":", ".join(reasons) or "policy match"})
    return {"policy":dict(p),"candidates":candidates,"count":len(candidates),"bytes":sum(x["size"] for x in candidates)}

def retention_apply(policy_id):
    preview=retention_preview(policy_id);deleted=0;details=[]
    stamp=datetime.now().strftime("%Y%m%d-%H%M%S");runtrash=TRASH/stamp;runtrash.mkdir(parents=True,exist_ok=True)
    with cx() as c:
        for x in preview["candidates"]:
            src=Path(x["path"])
            if src.exists() and src.is_file():
                target=runtrash/src.name
                n=1
                while target.exists():
                    target=runtrash/f"{src.stem}-{n}{src.suffix}";n+=1
                shutil.move(str(src),str(target))
                c.execute("UPDATE episodes SET location=NULL,file_size=0,status='Archived' WHERE id=?",(x["episode_id"],))
                details.append({**x,"trash_path":str(target)});deleted+=1
        c.execute("""INSERT INTO retention_runs(policy_id,dry_run,candidates,bytes_reclaimable,deleted,details_json)
                     VALUES(?,0,?,?,?,?)""",(policy_id,preview["count"],preview["bytes"],deleted,json.dumps(details)))
        c.commit()
    return {"deleted":deleted,"trash":str(runtrash),"preview":preview}

def set_watched(eid,percent=100,profile="default",source="manual"):
    with cx() as c:
        c.execute("""INSERT INTO watched_state(episode_id,profile,played_percent,watched_at,source)
                     VALUES(?,?,?,?,?) ON CONFLICT(episode_id,profile) DO UPDATE SET
                     played_percent=excluded.played_percent,watched_at=excluded.watched_at,source=excluded.source""",
                  (eid,profile,float(percent),datetime.now().isoformat(),source));c.commit()

def system_health():
    checks=[]
    def add(name,status,detail): checks.append({"name":name,"status":status,"detail":detail})
    try:
        with cx() as c:
            c.execute("PRAGMA quick_check"); add("Database","OK","SQLite quick check completed")
            shows=c.execute("SELECT COUNT(*) c FROM shows").fetchone()["c"]
            eps=c.execute("SELECT COUNT(*) c FROM episodes").fetchone()["c"]
            add("Library","OK",f"{shows} shows / {eps} episodes indexed")
    except Exception as e:add("Database","ERROR",str(e))
    try:
        test=BASE/".write-test";test.write_text("ok");test.unlink();add("Application data","OK","Application directory is writable")
    except Exception as e:add("Application data","ERROR",str(e))
    env=BASE/".env";add("Environment","OK" if env.exists() else "WARN",".env present" if env.exists() else ".env not found")
    with cx() as c:
        for x in checks:c.execute("INSERT INTO system_checks(check_name,status,detail) VALUES(?,?,?)",(x["name"],x["status"],x["detail"]))
        c.commit()
    return checks

def api_summary():
    return {
      "version":"17.2.0",
      "endpoints":[
        {"method":"GET","path":"/api/shows","purpose":"Search/list shows"},
        {"method":"GET","path":"/api/shows/{id}","purpose":"Show details"},
        {"method":"GET","path":"/api/shows/{id}/episodes","purpose":"Seasons/episodes"},
        {"method":"POST","path":"/api/episodes/{id}/search","purpose":"Interactive episode search"},
        {"method":"POST","path":"/api/search-results/{id}/grab","purpose":"Grab release"},
        {"method":"GET","path":"/api/queue/triage","purpose":"Queue"},
        {"method":"GET","path":"/api/provider-health","purpose":"Provider diagnostics"},
        {"method":"GET","path":"/api/operations/summary","purpose":"System operations"},
        {"method":"GET","path":"/api/version","purpose":"Running application version"},
        {"method":"GET","path":"/api/routes","purpose":"Registered route diagnostics"},
        {"method":"GET","path":"/api/library/health-report","purpose":"Library health report for migration validation"},
        {"method":"GET","path":"/api/retention/{id}/preview","purpose":"Safe retention preview"},
        {"method":"POST","path":"/api/retention/{id}/apply","purpose":"Apply retention to managed trash"}
      ]
    }
