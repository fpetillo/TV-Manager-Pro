from __future__ import annotations
from datetime import date
from pathlib import Path
import os
import time
import requests
import dbcore

BASE=Path(__file__).resolve().parent
DB=BASE/"tvmanager.db"

def cx():
    return dbcore.connect(DB)

def init():
    with cx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS metadata_refresh_state(
          show_id INTEGER PRIMARY KEY,
          last_refresh TEXT,
          last_status TEXT,
          last_error TEXT,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        c.commit()

def _setting(section,name,default=None):
    with cx() as c:
        r=c.execute("""SELECT value FROM settings
                       WHERE lower(section)=lower(?) AND lower(name)=lower(?)""",(section,name)).fetchone()
    return default if not r else r["value"]

def _as_int(v,default):
    try:return int(str(v).strip())
    except:return default

def _token():
    return os.getenv("TMDB_BEARER_TOKEN","").strip()

def _tmdb(path,params=None):
    token=_token()
    if not token:raise RuntimeError("TMDB_BEARER_TOKEN is not configured")
    r=requests.get("https://api.themoviedb.org/3"+path,
                   headers={"Authorization":"Bearer "+token,"accept":"application/json"},
                   params=params or {},timeout=20)
    r.raise_for_status()
    return r.json()

def resolve_tmdb(show):
    if show["tmdb_id"]:return int(show["tmdb_id"])
    imdb=(show["imdb_id"] or "").strip()
    if imdb:
        try:
            d=_tmdb("/find/"+imdb,{"external_source":"imdb_id"})
            rows=d.get("tv_results") or []
            if rows:return int(rows[0]["id"])
        except Exception:pass
    if show["tvdb_id"]:
        try:
            d=_tmdb("/find/"+str(show["tvdb_id"]),{"external_source":"tvdb_id"})
            rows=d.get("tv_results") or []
            if rows:return int(rows[0]["id"])
        except Exception:pass
    return None

def refresh_show(show_id):
    with cx() as c:
        show=c.execute("SELECT * FROM shows WHERE id=?",(int(show_id),)).fetchone()
    if not show:raise ValueError("Show not found")
    tmdb_id=resolve_tmdb(show)
    if not tmdb_id:raise ValueError("Could not resolve show to TMDb")

    info=_tmdb(f"/tv/{tmdb_id}",{"language":"en-US","append_to_response":"external_ids"})
    ext=info.get("external_ids") or {}
    poster_path=info.get("poster_path")
    genres=", ".join(x.get("name","") for x in info.get("genres",[]) if x.get("name"))
    networks=", ".join(x.get("name","") for x in info.get("networks",[]) if x.get("name"))
    inserted=0;updated=0
    today=date.today().isoformat()

    # Fetch remote season payloads before opening the write transaction so
    # metadata network latency never holds a SQLite writer lock.
    season_payloads=[]
    for season in info.get("seasons",[]):
        sn=season.get("season_number")
        if sn is None:continue
        try:
            sd=_tmdb(f"/tv/{tmdb_id}/season/{sn}",{"language":"en-US"})
            season_payloads.append((sn,sd))
        except Exception:
            continue
        time.sleep(0.10)

    with cx() as c:
        c.execute("""UPDATE shows SET
          tmdb_id=?,imdb_id=COALESCE(NULLIF(?,''),imdb_id),tvdb_id=COALESCE(?,tvdb_id),
          name=?,original_name=?,first_air_date=?,overview=?,poster=?,vote_average=?,
          network=?,genre=? WHERE id=?""",
          (tmdb_id,ext.get("imdb_id"),ext.get("tvdb_id"),info.get("name") or show["name"],
           info.get("original_name"),info.get("first_air_date"),info.get("overview") or "",
           ("https://image.tmdb.org/t/p/w500"+poster_path if poster_path else show["poster"]),
           info.get("vote_average"),networks or show["network"],genres or show["genre"],show_id))

        for sn,sd in season_payloads:
            for ep in sd.get("episodes",[]):
                en=ep.get("episode_number")
                if en is None:continue
                existing=c.execute("""SELECT id,location,status FROM episodes
                                      WHERE show_id=? AND season=? AND episode=?""",
                                   (show_id,sn,en)).fetchone()
                air=ep.get("air_date")
                default_status="Unaired" if air and air>today else "Wanted"
                if existing:
                    c.execute("""UPDATE episodes SET name=COALESCE(NULLIF(?,''),name),
                                 airdate=COALESCE(NULLIF(?,''),airdate) WHERE id=?""",
                              (ep.get("name"),air,existing["id"]))
                    updated+=1
                else:
                    c.execute("""INSERT INTO episodes(show_id,season,episode,name,airdate,status)
                                 VALUES(?,?,?,?,?,?)""",(show_id,sn,en,ep.get("name"),air,default_status))
                    inserted+=1
        c.execute("""INSERT INTO metadata_refresh_state(show_id,last_refresh,last_status,last_error,updated_at)
                     VALUES(?,CURRENT_TIMESTAMP,'OK',NULL,CURRENT_TIMESTAMP)
                     ON CONFLICT(show_id) DO UPDATE SET
                       last_refresh=CURRENT_TIMESTAMP,last_status='OK',last_error=NULL,updated_at=CURRENT_TIMESTAMP""",
                  (show_id,))
        c.commit()
    return {"show_id":show_id,"name":info.get("name") or show["name"],
            "tmdb_id":tmdb_id,"inserted":inserted,"updated":updated}

def refresh_batch(limit=None):
    update_hours=max(1,_as_int(_setting("General","update_frequency","168"),168))
    batch=max(1,min(10,_as_int(limit if limit is not None else _setting("TVManager","metadata_batch_size","3"),3)))
    with cx() as c:
        rows=c.execute("""SELECT s.id,s.name FROM shows s
                          LEFT JOIN metadata_refresh_state m ON m.show_id=s.id
                          WHERE COALESCE(s.paused,0)=0 AND COALESCE(s.metadata_enabled,1)=1
                          AND (m.last_refresh IS NULL OR m.last_refresh<=datetime(CURRENT_TIMESTAMP,?))
                          ORDER BY CASE WHEN m.last_refresh IS NULL THEN 0 ELSE 1 END,
                                   COALESCE(m.last_refresh,'1900-01-01'),s.name
                          LIMIT ?""",(f"-{update_hours} hours",batch)).fetchall()
    results=[]
    for row in rows:
        try:
            results.append({"ok":True,**refresh_show(row["id"])})
        except Exception as ex:
            with cx() as c:
                c.execute("""INSERT INTO metadata_refresh_state(show_id,last_status,last_error,updated_at)
                             VALUES(?,'Error',?,CURRENT_TIMESTAMP)
                             ON CONFLICT(show_id) DO UPDATE SET
                               last_status='Error',last_error=excluded.last_error,updated_at=CURRENT_TIMESTAMP""",
                          (row["id"],str(ex)[:1000]))
                c.commit()
            results.append({"ok":False,"show_id":row["id"],"name":row["name"],"error":str(ex)})
    return {"eligible_selected":len(rows),"batch_size":batch,"update_hours":update_hours,"results":results}
