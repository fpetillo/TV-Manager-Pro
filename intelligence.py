from __future__ import annotations
import dbcore
import json, os, re, sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BASE=Path(__file__).resolve().parent
DB=BASE/"tvmanager.db"

def cx():
    return dbcore.connect(DB)

def init():
    with cx() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS tags(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          color TEXT DEFAULT 'slate'
        );
        CREATE TABLE IF NOT EXISTS show_tags(
          show_id INTEGER NOT NULL,
          tag_id INTEGER NOT NULL,
          PRIMARY KEY(show_id,tag_id)
        );
        CREATE TABLE IF NOT EXISTS saved_filters(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          query_json TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS retention_policies(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          keep_latest INTEGER DEFAULT 0,
          keep_days INTEGER DEFAULT 0,
          keep_watched INTEGER DEFAULT 1,
          delete_unwatched INTEGER DEFAULT 0,
          enabled INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS season_pack_candidates(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          show_id INTEGER NOT NULL,
          season INTEGER NOT NULL,
          provider TEXT,
          title TEXT,
          url TEXT,
          guid TEXT,
          size INTEGER,
          seeders INTEGER,
          quality TEXT,
          score REAL DEFAULT 0,
          episode_count INTEGER DEFAULT 0,
          covered_json TEXT,
          status TEXT DEFAULT 'Found',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS queue_notes(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          download_id INTEGER NOT NULL,
          note TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS episode_locks(
          episode_id INTEGER PRIMARY KEY,
          locked INTEGER DEFAULT 1,
          reason TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS command_history(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          command TEXT NOT NULL,
          context_json TEXT,
          executed_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cols={r["name"] for r in c.execute("PRAGMA table_info(shows)").fetchall()}
        for name,definition in {
            "favorite":"INTEGER DEFAULT 0",
            "retention_policy_id":"INTEGER",
            "display_sort":"TEXT",
        }.items():
            if name not in cols:c.execute(f'ALTER TABLE shows ADD COLUMN "{name}" {definition}')
        c.commit()

def tags():
    with cx() as c:
        return [dict(r) for r in c.execute("""SELECT t.*,COUNT(st.show_id) show_count
                    FROM tags t LEFT JOIN show_tags st ON st.tag_id=t.id
                    GROUP BY t.id ORDER BY t.name COLLATE NOCASE""").fetchall()]

def save_tag(name,color="slate", tag_id=None):
    name=(name or "Tag").strip() or "Tag"
    with cx() as c:
        if tag_id:
            c.execute("UPDATE tags SET name=?,color=? WHERE id=?",(name,color,int(tag_id)))
            tid=int(tag_id)
        else:
            c.execute("""INSERT INTO tags(name,color) VALUES(?,?)
                         ON CONFLICT(name) DO UPDATE SET color=excluded.color""",(name,color))
            tid=c.execute("SELECT id FROM tags WHERE name=?",(name,)).fetchone()["id"]
        c.commit()
        return tid

def delete_tag(tag_id):
    with cx() as c:
        c.execute("DELETE FROM show_tags WHERE tag_id=?",(int(tag_id),))
        cur=c.execute("DELETE FROM tags WHERE id=?",(int(tag_id),))
        c.commit()
    if cur.rowcount == 0:
        raise ValueError("Tag not found")
    return {"ok": True, "deleted": int(tag_id)}

def set_show_tags(show_id,tag_ids):
    with cx() as c:
        c.execute("DELETE FROM show_tags WHERE show_id=?",(show_id,))
        c.executemany("INSERT OR IGNORE INTO show_tags(show_id,tag_id) VALUES(?,?)",
                      [(show_id,int(t)) for t in tag_ids])
        c.commit()

def tags_for_show(show_id):
    with cx() as c:
        return [dict(r) for r in c.execute("""SELECT t.* FROM tags t JOIN show_tags st ON st.tag_id=t.id
                                             WHERE st.show_id=? ORDER BY t.name""",(show_id,)).fetchall()]

def saved_filters():
    with cx() as c:
        rows=c.execute("SELECT * FROM saved_filters ORDER BY name").fetchall()
    out=[]
    for r in rows:
        d=dict(r)
        try:d["query"]=json.loads(d.pop("query_json"))
        except Exception:d["query"]={}
        out.append(d)
    return out

def save_filter(name,query):
    raw=json.dumps(query,sort_keys=True)
    with cx() as c:
        c.execute("""INSERT INTO saved_filters(name,query_json) VALUES(?,?)
                     ON CONFLICT(name) DO UPDATE SET query_json=excluded.query_json""",(name,raw))
        c.commit()

def retention_policies():
    with cx() as c:return [dict(r) for r in c.execute("SELECT * FROM retention_policies ORDER BY name").fetchall()]

def delete_retention(pid):
    with cx() as c:
        c.execute("UPDATE shows SET retention_policy_id=NULL WHERE retention_policy_id=?",(int(pid),))
        cur=c.execute("DELETE FROM retention_policies WHERE id=?",(int(pid),))
        c.commit()
    if cur.rowcount == 0:
        raise ValueError("Retention policy not found")
    return {"ok": True, "deleted": int(pid)}

def save_retention(d):
    with cx() as c:
        if d.get("id"):
            c.execute("""UPDATE retention_policies SET name=?,keep_latest=?,keep_days=?,keep_watched=?,delete_unwatched=?,enabled=? WHERE id=?""",
                      (d["name"],int(d.get("keep_latest",0)),int(d.get("keep_days",0)),1 if d.get("keep_watched",True) else 0,
                       1 if d.get("delete_unwatched",False) else 0,1 if d.get("enabled",False) else 0,d["id"]))
            rid=d["id"]
        else:
            cur=c.execute("""INSERT INTO retention_policies(name,keep_latest,keep_days,keep_watched,delete_unwatched,enabled)
                             VALUES(?,?,?,?,?,?)""",
                          (d["name"],int(d.get("keep_latest",0)),int(d.get("keep_days",0)),1 if d.get("keep_watched",True) else 0,
                           1 if d.get("delete_unwatched",False) else 0,1 if d.get("enabled",False) else 0))
            rid=cur.lastrowid
        c.commit();return rid

def lock_episode(eid,locked=True,reason="Protected from automated deletion/replacement"):
    with cx() as c:
        if locked:
            c.execute("""INSERT INTO episode_locks(episode_id,locked,reason) VALUES(?,1,?)
                         ON CONFLICT(episode_id) DO UPDATE SET locked=1,reason=excluded.reason""",(eid,reason))
        else:c.execute("DELETE FROM episode_locks WHERE episode_id=?",(eid,))
        c.commit()

def locked(eid):
    with cx() as c:return bool(c.execute("SELECT 1 FROM episode_locks WHERE episode_id=? AND locked=1",(eid,)).fetchone())

def command_search(q,limit=12):
    q=(q or "").strip()
    if not q:return []
    like=f"%{q}%"
    out=[]
    with cx() as c:
        shows=c.execute("""SELECT id,name,poster,status FROM shows
                           WHERE name LIKE ? COLLATE NOCASE OR COALESCE(imdb_id,'') LIKE ?
                           ORDER BY favorite DESC,name LIMIT ?""",(like,like,limit)).fetchall()
        for s in shows:out.append({"type":"show","id":s["id"],"title":s["name"],"subtitle":s["status"] or "Show","href":f"/manager?show={s['id']}"})
        eps=c.execute("""SELECT e.id,e.season,e.episode,e.name,s.name show_name FROM episodes e JOIN shows s ON s.id=e.show_id
                         WHERE e.name LIKE ? COLLATE NOCASE OR s.name LIKE ? COLLATE NOCASE
                         ORDER BY COALESCE(e.airdate,'') DESC LIMIT ?""",(like,like,max(0,limit-len(out)))).fetchall()
        for e in eps:out.append({"type":"episode","id":e["id"],"title":f'{e["show_name"]} S{e["season"]:02d}E{e["episode"]:02d}',"subtitle":e["name"] or "Episode","href":f"/manager?show={c.execute('SELECT show_id FROM episodes WHERE id=?',(e['id'],)).fetchone()['show_id']}"})
    static=[
      ("Dashboard","/dashboard"),("Missing Episodes","/missing"),("Upcoming Episodes","/upcoming"),
      ("SickChill Manage","/manage"),("Manage Searches","/manage"),("Episode Status Management","/manage"),
      ("Failed Downloads","/manage"),("Scene Exceptions","/manage"),
      ("Subtitles","/subtitles"),("Post Processing","/postprocess"),("Quality Profiles","/quality"),
      ("Operations","/operations"),("Database Safety","/database-safety"),("Advanced","/advanced"),("Settings","/settings")
    ]
    for title,href in static:
        if q.lower() in title.lower() and len(out)<limit:out.append({"type":"page","title":title,"subtitle":"Navigation","href":href})
    return out[:limit]

def record_command(command,context=None):
    with cx() as c:
        c.execute("INSERT INTO command_history(command,context_json) VALUES(?,?)",(command,json.dumps(context or {})));c.commit()

def dashboard_insights():
    items=[]
    with cx() as c:
        wanted=c.execute("SELECT COUNT(*) c FROM episodes WHERE lower(COALESCE(status,'')) IN ('wanted','failed')").fetchone()["c"]
        missing_paths=c.execute("""SELECT COUNT(*) c FROM shows WHERE location IS NOT NULL AND trim(location)<>''""").fetchone()["c"]
        failed=c.execute("SELECT COUNT(*) c FROM downloads WHERE status='Failed'").fetchone()["c"]
        snatched=c.execute("SELECT COUNT(*) c FROM episodes WHERE lower(COALESCE(status,''))='snatched'").fetchone()["c"]
        locks=c.execute("SELECT COUNT(*) c FROM episode_locks WHERE locked=1").fetchone()["c"]
    if wanted:items.append({"severity":"info","title":f"{wanted} episodes need attention","detail":"Wanted or failed episodes are waiting for search/download decisions.","href":"/missing"})
    if failed:items.append({"severity":"warn","title":f"{failed} download failures","detail":"Review failed releases and retry or blacklist them.","href":"/activity"})
    if snatched:items.append({"severity":"info","title":f"{snatched} episodes currently snatched","detail":"Downloader polling will reconcile completion state.","href":"/activity"})
    if locks:items.append({"severity":"good","title":f"{locks} protected episodes","detail":"Locked episodes are protected from future retention actions.","href":"/manager"})
    if not items:items.append({"severity":"good","title":"Library looks calm","detail":"No obvious queue or backlog issues need attention.","href":"/dashboard"})
    return items

def queue_triage():
    with cx() as c:
        rows=c.execute("""SELECT d.*,s.name show_name,e.season,e.episode,
                                 (SELECT note FROM queue_notes qn WHERE qn.download_id=d.id ORDER BY qn.id DESC LIMIT 1) latest_note
                          FROM downloads d
                          LEFT JOIN episodes e ON e.id=d.episode_id
                          LEFT JOIN shows s ON s.id=e.show_id
                          ORDER BY CASE d.status WHEN 'Failed' THEN 0 WHEN 'Queued' THEN 1 WHEN 'Completed' THEN 3 ELSE 2 END,d.id DESC
                          LIMIT 500""").fetchall()
    return [dict(r) for r in rows]

def add_queue_note(download_id,note):
    with cx() as c:c.execute("INSERT INTO queue_notes(download_id,note) VALUES(?,?)",(download_id,note));c.commit()

def _season_pack_title(show,season):
    return f'{show["name"]} S{season:02d}'

def season_pack_plan(show_id,season):
    with cx() as c:
        show=c.execute("SELECT * FROM shows WHERE id=?",(show_id,)).fetchone()
        eps=c.execute("""SELECT id,episode,status,location,airdate FROM episodes
                         WHERE show_id=? AND season=? ORDER BY episode""",(show_id,season)).fetchall()
    if not show:raise ValueError("Show not found")
    needed=[e for e in eps if (not e["location"]) and str(e["status"] or "").lower() in {"wanted","failed"}]
    return {"show":show["name"],"show_id":show_id,"season":season,"total_episodes":len(eps),
            "needed_episodes":[e["episode"] for e in needed],"needed_count":len(needed),
            "season_pack_preferred":len(needed)>=max(3,int(len(eps)*0.6)) if eps else False}

def filter_library(query):
    q=query or {}
    where=[];params=[]
    text=(q.get("text") or "").strip()
    if text:
        like=f"%{text}%";where.append("(s.name LIKE ? COLLATE NOCASE OR COALESCE(s.network,'') LIKE ? COLLATE NOCASE)");params.extend([like,like])
    if q.get("favorite"):where.append("COALESCE(s.favorite,0)=1")
    if q.get("paused") is True:where.append("COALESCE(s.paused,0)=1")
    if q.get("paused") is False:where.append("COALESCE(s.paused,0)=0")
    if q.get("tag_id"):
        where.append("EXISTS(SELECT 1 FROM show_tags st WHERE st.show_id=s.id AND st.tag_id=?)");params.append(int(q["tag_id"]))
    sql="""SELECT s.*,
            (SELECT COUNT(*) FROM episodes e WHERE e.show_id=s.id) episode_count,
            (SELECT COUNT(*) FROM episodes e WHERE e.show_id=s.id AND lower(COALESCE(e.status,'')) IN ('wanted','failed')) wanted_count
           FROM shows s"""
    if where:sql+=" WHERE "+" AND ".join(where)
    sql+=" ORDER BY COALESCE(s.favorite,0) DESC,s.name COLLATE NOCASE"
    with cx() as c:rows=c.execute(sql,params).fetchall()
    return [dict(r) for r in rows]
