from __future__ import annotations
from datetime import datetime
from pathlib import Path
import json
import re
import shutil
import dbcore

BASE=Path(__file__).resolve().parent
DB=BASE/"tvmanager.db"
TRASH=BASE/"managed_trash"/"upgrades"

STATES=("Found","Queued","Downloading","Downloaded","Importing","Completed","Failed","Blocked","Quarantined","Superseded")
TRANSITIONS={
    "Found":{"Queued","Blocked"},
    "Queued":{"Downloading","Downloaded","Failed","Blocked"},
    "Downloading":{"Downloaded","Failed","Blocked"},
    "Downloaded":{"Importing","Failed","Blocked"},
    "Importing":{"Completed","Failed","Quarantined"},
    "Completed":{"Superseded"},
    "Failed":{"Queued","Blocked"},
    "Blocked":{"Queued"},
    "Quarantined":{"Queued","Failed"},
    "Superseded":set(),
}

def cx():
    return dbcore.connect(DB)

def _setting_bool(section, name, default=False):
    try:
        with cx() as c:
            r = c.execute("SELECT value FROM settings WHERE lower(section)=lower(?) AND lower(name)=lower(?)", (section, name)).fetchone()
        if not r or r["value"] is None:
            return default
        return str(r["value"]).strip().lower() in {"1", "true", "yes", "on"}
    except Exception:
        return default

def _episode_scope_filter(ignore_specials):
    return " AND COALESCE(e2.season,0)<>0" if ignore_specials else ""

def _missing_episode_summary(show_id, ignore_specials=False, limit=10):
    filt = " AND COALESCE(season,0)<>0" if ignore_specials else ""
    with cx() as c:
        rows = c.execute(f"""SELECT season,episode FROM episodes
                            WHERE show_id=? {filt}
                              AND (location IS NULL OR TRIM(location)='')
                            ORDER BY season,episode LIMIT ?""", (int(show_id), int(limit)+1)).fetchall()
    codes = [f"S{int(r['season']):02d}E{int(r['episode']):02d}" for r in rows[:limit]]
    more = max(0, len(rows)-limit)
    return ", ".join(codes) + (f" +{more} more" if more else "") if codes else "Complete"

def init():
    with cx() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS acquisition_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          acquisition_type TEXT NOT NULL,
          acquisition_id INTEGER NOT NULL,
          from_state TEXT,
          to_state TEXT NOT NULL,
          message TEXT,
          details_json TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_acquisition_events
          ON acquisition_events(acquisition_type,acquisition_id,id);
        CREATE TABLE IF NOT EXISTS upgrade_replacements(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          episode_id INTEGER NOT NULL,
          old_path TEXT,
          replacement_path TEXT,
          trash_path TEXT,
          old_release TEXT,
          new_release TEXT,
          old_quality TEXT,
          new_quality TEXT,
          status TEXT DEFAULT 'Pending',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          completed_at TEXT,
          restored_at TEXT
        );
        """)
        c.commit()

def transition(acquisition_type, acquisition_id, current, new, message=None, details=None, conn=None, force=False):
    current=(current or "Found").title()
    new=(new or "").title()
    if new not in STATES:
        raise ValueError(f"Unknown acquisition state: {new}")
    if current != new and not force and new not in TRANSITIONS.get(current,set()):
        raise ValueError(f"Invalid acquisition transition {current} -> {new}")
    owns=conn is None
    c=conn or cx()
    try:
        c.execute("""INSERT INTO acquisition_events(acquisition_type,acquisition_id,from_state,to_state,message,details_json)
                     VALUES(?,?,?,?,?,?)""",
                  (acquisition_type,int(acquisition_id),current,new,message,
                   json.dumps(details,default=str) if details is not None else None))
        if acquisition_type=="episode":
            c.execute("UPDATE downloads SET status=? WHERE id=?",(new,int(acquisition_id)))
        elif acquisition_type=="season_pack":
            c.execute("UPDATE season_pack_downloads SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(new,int(acquisition_id)))
        if owns:c.commit()
    finally:
        if owns:c.close()
    return new

def quality_rank(text):
    t=(text or "").lower()
    # Resolution dominates source/codec. This intentionally stays conservative.
    if "2160" in t or "4k" in t: base=400
    elif "1080" in t: base=300
    elif "720" in t: base=200
    elif "480" in t or "sd" in t: base=100
    else: base=0
    if "bluray" in t or "blu-ray" in t:base+=40
    elif "web-dl" in t or "webdl" in t:base+=30
    elif "webrip" in t:base+=20
    elif "hdtv" in t:base+=10
    if "repack" in t:base+=4
    elif "proper" in t:base+=3
    return base

def replacement_allowed(old_quality,old_release,new_quality,new_release):
    old=quality_rank(" ".join(filter(None,[old_quality,old_release])))
    new=quality_rank(" ".join(filter(None,[new_quality,new_release])))
    # Unknown incoming quality may replace unknown current quality, but never a recognized better file.
    if new==0 and old>0:return False,"Incoming quality could not be verified"
    if new<old:return False,f"Would downgrade quality ({new} < {old})"
    if new==old:
        nt=(new_release or "").upper();ot=(old_release or "").upper()
        corrective=("PROPER" in nt or "REPACK" in nt) and not ("PROPER" in ot or "REPACK" in ot)
        if not corrective:return False,"Replacement is not higher quality or a corrective release"
    return True,"Upgrade accepted"

def stage_replacement(episode, incoming_path, new_release=None, new_quality=None):
    old_path=Path(episode["location"]) if episode["location"] else None
    if not old_path or not old_path.exists() or not old_path.is_file():
        return {"allowed":True,"replacement_id":None,"trash_path":None}
    allowed,reason=replacement_allowed(episode["quality"],episode["release_name"],new_quality,new_release)
    if not allowed:
        return {"allowed":False,"reason":reason}
    stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
    target_dir=TRASH/stamp
    target_dir.mkdir(parents=True,exist_ok=True)
    target=target_dir/old_path.name
    n=1
    while target.exists():
        target=target_dir/f"{old_path.stem}-{n}{old_path.suffix}";n+=1
    shutil.move(str(old_path),str(target))
    with cx() as c:
        cur=c.execute("""INSERT INTO upgrade_replacements(
                          episode_id,old_path,replacement_path,trash_path,old_release,new_release,old_quality,new_quality,status)
                         VALUES(?,?,?,?,?,?,?,?,?)""",
                      (episode["id"],str(old_path),str(incoming_path),str(target),
                       episode["release_name"],new_release,episode["quality"],new_quality,"Staged"))
        rid=cur.lastrowid;c.commit()
    return {"allowed":True,"replacement_id":rid,"trash_path":str(target),"reason":reason}

def complete_replacement(replacement_id, final_path):
    if not replacement_id:return
    with cx() as c:
        c.execute("""UPDATE upgrade_replacements SET replacement_path=?,status='Completed',
                     completed_at=CURRENT_TIMESTAMP WHERE id=?""",(str(final_path),int(replacement_id)))
        c.commit()

def rollback_replacement(replacement_id):
    with cx() as c:
        r=c.execute("SELECT * FROM upgrade_replacements WHERE id=?",(int(replacement_id),)).fetchone()
    if not r:raise ValueError("Replacement not found")
    trash=Path(r["trash_path"] or "");old=Path(r["old_path"] or "")
    if not trash.exists():raise ValueError("Original file is no longer available in managed trash")
    old.parent.mkdir(parents=True,exist_ok=True)
    replacement=Path(r["replacement_path"] or "")
    if replacement.exists() and replacement.is_file():
        qdir=BASE/"managed_trash"/"rollback_replaced"
        qdir.mkdir(parents=True,exist_ok=True)
        shutil.move(str(replacement),str(qdir/replacement.name))
    shutil.move(str(trash),str(old))
    with cx() as c:
        c.execute("""UPDATE episodes SET location=?,release_name=?,quality=?,status='Downloaded'
                     WHERE id=?""",(str(old),r["old_release"],r["old_quality"],r["episode_id"]))
        c.execute("UPDATE upgrade_replacements SET status='RolledBack',restored_at=CURRENT_TIMESTAMP WHERE id=?",(r["id"],))
        c.commit()
    return {"ok":True,"restored":str(old)}

def unified_queue(limit=300):
    ignore_specials = _setting_bool("TVManager", "ignore_season_zero_counts", True)
    scope = _episode_scope_filter(ignore_specials)
    with cx() as c:
        eps=[dict(r) for r in c.execute(f"""SELECT d.id,'episode' acquisition_type,d.status,d.client,d.release_name title,
                      d.external_id,d.added_at created_at,e.id episode_id,e.season,e.episode,e.show_id,s.name show_name,
                      (SELECT COUNT(*) FROM episodes e2 WHERE e2.show_id=s.id {scope}) episode_total,
                      (SELECT COUNT(*) FROM episodes e2 WHERE e2.show_id=s.id {scope} AND e2.location IS NOT NULL AND TRIM(e2.location)<>'') downloaded_total,
                      (SELECT COUNT(*) FROM episodes e2 WHERE e2.show_id=s.id {scope} AND (e2.location IS NULL OR TRIM(e2.location)='')) missing_total
                      FROM downloads d JOIN episodes e ON e.id=d.episode_id JOIN shows s ON s.id=e.show_id
                      WHERE d.status NOT IN ('Completed','Superseded') ORDER BY d.id DESC LIMIT ?""",(int(limit),)).fetchall()]
        packs=[dict(r) for r in c.execute(f"""SELECT p.id,'season_pack' acquisition_type,p.status,p.client,p.title,
                      p.external_id,p.created_at,NULL episode_id,p.season,NULL episode,p.show_id,s.name show_name,
                      (SELECT COUNT(*) FROM episodes e2 WHERE e2.show_id=s.id {scope}) episode_total,
                      (SELECT COUNT(*) FROM episodes e2 WHERE e2.show_id=s.id {scope} AND e2.location IS NOT NULL AND TRIM(e2.location)<>'') downloaded_total,
                      (SELECT COUNT(*) FROM episodes e2 WHERE e2.show_id=s.id {scope} AND (e2.location IS NULL OR TRIM(e2.location)='')) missing_total
                      FROM season_pack_downloads p JOIN shows s ON s.id=p.show_id
                      WHERE p.status NOT IN ('Completed','Superseded') ORDER BY p.id DESC LIMIT ?""",(int(limit),)).fetchall()]
    rows=eps+packs
    for row in rows:
        row["ignore_season_zero_counts"] = ignore_specials
        try:
            row["missing_episode_numbers"] = _missing_episode_summary(row.get("show_id"), ignore_specials)
        except Exception:
            row["missing_episode_numbers"] = ""
        total = int(row.get("episode_total") or 0)
        got = int(row.get("downloaded_total") or 0)
        row["download_percent"] = round((got/total)*100, 4) if total else 0
    # SickChill-style triage: biggest missing shows first, then highest downloaded totals.
    rows.sort(key=lambda x:(int(x.get("missing_total") or 0), int(x.get("downloaded_total") or 0), int(x.get("episode_total") or 0), x.get("show_name") or ""), reverse=True)
    return rows[:int(limit)]

