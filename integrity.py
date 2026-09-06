from __future__ import annotations
from pathlib import Path
import hashlib
import os
import dbcore

BASE=Path(__file__).resolve().parent
DB=BASE/"tvmanager.db"
CHUNK=1024*1024

def cx():
    return dbcore.connect(DB)

def init():
    with cx() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS media_fingerprints(
          path TEXT PRIMARY KEY,
          file_size INTEGER NOT NULL,
          mtime_ns INTEGER,
          fingerprint TEXT NOT NULL,
          episode_id INTEGER,
          checked_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_media_fingerprint ON media_fingerprints(fingerprint,file_size);
        """)
        c.commit()

def fingerprint(path):
    p=Path(path)
    st=p.stat()
    size=st.st_size
    h=hashlib.sha256()
    h.update(str(size).encode())
    with p.open("rb") as f:
        h.update(f.read(CHUNK))
        if size>CHUNK:
            f.seek(max(0,size-CHUNK))
            h.update(f.read(CHUNK))
    return h.hexdigest(),size,st.st_mtime_ns

def cache_fingerprint(path,episode_id=None):
    p=Path(path)
    st=p.stat()
    with cx() as c:
        old=c.execute("SELECT * FROM media_fingerprints WHERE path=?",(str(p),)).fetchone()
        if old and old["file_size"]==st.st_size and old["mtime_ns"]==st.st_mtime_ns:
            return dict(old)
    fp,size,mtime=fingerprint(p)
    with cx() as c:
        c.execute("""INSERT INTO media_fingerprints(path,file_size,mtime_ns,fingerprint,episode_id,checked_at)
                     VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
                     ON CONFLICT(path) DO UPDATE SET file_size=excluded.file_size,mtime_ns=excluded.mtime_ns,
                     fingerprint=excluded.fingerprint,episode_id=excluded.episode_id,checked_at=CURRENT_TIMESTAMP""",
                  (str(p),size,mtime,fp,episode_id))
        c.commit()
    return {"path":str(p),"file_size":size,"mtime_ns":mtime,"fingerprint":fp,"episode_id":episode_id}

def duplicate_content(limit=500):
    with cx() as c:
        rows=c.execute("""SELECT e.id episode_id,e.location,s.name show_name,e.season,e.episode
                          FROM episodes e JOIN shows s ON s.id=e.show_id
                          WHERE e.location IS NOT NULL AND trim(e.location)<>'' LIMIT ?""",(int(limit),)).fetchall()
    checked=[]
    for r in rows:
        p=Path(r["location"])
        if not p.exists() or not p.is_file():continue
        try:
            item=cache_fingerprint(p,r["episode_id"])
            item.update({"show_name":r["show_name"],"season":r["season"],"episode":r["episode"]})
            checked.append(item)
        except OSError:
            continue
    groups={}
    for x in checked:
        groups.setdefault((x["fingerprint"],x["file_size"]),[]).append(x)
    return [g for g in groups.values() if len({x["path"] for x in g})>1]
