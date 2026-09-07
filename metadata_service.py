from __future__ import annotations
from datetime import date
from pathlib import Path
import os
import sqlite3
import time
import dbcore
import tmdb_client
import job_center
import requests

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
        # v17.15: episode artwork and richer metadata fields. These are safe
        # no-op upgrades for existing imported SickChill libraries.
        tables = {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "episodes" in tables:
            cols = {r["name"] for r in c.execute('PRAGMA table_info("episodes")').fetchall()}
            for name, definition in {
                "overview": "TEXT",
                "still_url": "TEXT",
                "still_path": "TEXT",
                "tmdb_episode_id": "INTEGER",
                "metadata_updated_at": "TEXT",
            }.items():
                if name not in cols:
                    c.execute(f'ALTER TABLE episodes ADD COLUMN "{name}" {definition}')
        c.commit()

def _setting(section,name,default=None):
    with cx() as c:
        r=c.execute("""SELECT value FROM settings
                       WHERE lower(section)=lower(?) AND lower(name)=lower(?)""",(section,name)).fetchone()
    return default if not r else r["value"]

def _as_int(v,default):
    try:return int(str(v).strip())
    except:return default

def tmdb_status():
    return tmdb_client.configured(DB)

def _tmdb(path,params=None):
    return tmdb_client.get(path, params=params or {}, db_path=DB, timeout=20)


def _record_refresh_error(show_id, error):
    def op():
        with cx() as c:
            c.execute("""INSERT INTO metadata_refresh_state(show_id,last_status,last_error,updated_at)
                         VALUES(?,'Error',?,CURRENT_TIMESTAMP)
                         ON CONFLICT(show_id) DO UPDATE SET last_status='Error',last_error=excluded.last_error,updated_at=CURRENT_TIMESTAMP""",
                      (show_id,str(error)[:1000]))
            c.commit()
    try:
        return dbcore.retry(op, attempts=8)
    except sqlite3.OperationalError as locked:
        if not dbcore.is_lock_error(locked):
            raise
        # Do not crash the whole background refresh because the error-state log
        # itself was blocked by another process. The primary error is already
        # returned in the job result and visible in Active Jobs.
        return None

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
    import show_preferences
    with cx() as c:
        show=c.execute("SELECT * FROM shows WHERE id=?",(int(show_id),)).fetchone()
    if not show:raise ValueError("Show not found")
    language=dict(show).get("metadata_language") or "en-US"
    tmdb_id=resolve_tmdb(show)
    if not tmdb_id:raise ValueError("Could not resolve show to TMDb")

    info=_tmdb(f"/tv/{tmdb_id}",{"language":language,"append_to_response":"external_ids"})
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
            sd=_tmdb(f"/tv/{tmdb_id}/season/{sn}",{"language":language})
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
                still_path=ep.get("still_path")
                still_url=("https://image.tmdb.org/t/p/w500"+still_path) if still_path else None
                default_status=show_preferences.initial_episode_status(show,air,today)
                if existing:
                    c.execute("""UPDATE episodes SET
                                 name=COALESCE(NULLIF(?,''),name),
                                 airdate=COALESCE(NULLIF(?,''),airdate),
                                 overview=COALESCE(NULLIF(?,''),overview),
                                 still_url=COALESCE(NULLIF(?,''),still_url),
                                 tmdb_episode_id=COALESCE(?,tmdb_episode_id),
                                 metadata_updated_at=CURRENT_TIMESTAMP
                                 WHERE id=?""",
                              (ep.get("name"),air,ep.get("overview") or "",still_url,ep.get("id"),existing["id"]))
                    updated+=1
                else:
                    c.execute("""INSERT INTO episodes(show_id,season,episode,name,airdate,status,overview,still_url,tmdb_episode_id,metadata_updated_at)
                                 VALUES(?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",(show_id,sn,en,ep.get("name"),air,default_status,ep.get("overview") or "",still_url,ep.get("id")))
                    inserted+=1
        c.execute("""INSERT INTO metadata_refresh_state(show_id,last_refresh,last_status,last_error,updated_at)
                     VALUES(?,CURRENT_TIMESTAMP,'OK',NULL,CURRENT_TIMESTAMP)
                     ON CONFLICT(show_id) DO UPDATE SET
                       last_refresh=CURRENT_TIMESTAMP,last_status='OK',last_error=NULL,updated_at=CURRENT_TIMESTAMP""",
                  (show_id,))
        c.commit()
    scene_result=None
    if dict(show).get("scene_numbering"):
        try:
            import scene_sync
            scene_result=scene_sync.refresh(show_id)
        except ValueError as exc:scene_result={"error":str(exc)}
    return {"scene_mapping":scene_result,"show_id":show_id,"name":info.get("name") or show["name"],
            "tmdb_id":tmdb_id,"inserted":inserted,"updated":updated}

def refresh_batch(limit=None, batch_size=None):
    update_hours=max(1,_as_int(_setting("General","update_frequency","168"),168))
    requested = batch_size if batch_size is not None else limit
    batch=max(1,min(50,_as_int(requested if requested is not None else _setting("TVManager","metadata_batch_size","3"),3)))
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

# ---- v17.12 full-library metadata refresh jobs ----
import threading
import uuid
from datetime import datetime

_FULL_REFRESH_JOBS = {}
_FULL_REFRESH_LOCK = threading.RLock()

def _job_snapshot(job_id):
    with _FULL_REFRESH_LOCK:
        job = _FULL_REFRESH_JOBS.get(job_id)
        return dict(job) if job else None

def _set_job(job_id, **updates):
    with _FULL_REFRESH_LOCK:
        job = _FULL_REFRESH_JOBS.setdefault(job_id, {"job_id": job_id})
        job.update(updates)
        job["updated_at"] = datetime.now().isoformat(timespec="seconds")
        return dict(job)

def full_refresh_jobs():
    with _FULL_REFRESH_LOCK:
        return [dict(v) for v in sorted(_FULL_REFRESH_JOBS.values(), key=lambda x: x.get("created_at", ""), reverse=True)]

def full_refresh_job(job_id):
    return _job_snapshot(job_id)

def _eligible_show_ids(include_paused=False, stale_only=False):
    where = []
    params = []
    if not include_paused:
        where.append("COALESCE(s.paused,0)=0")
    where.append("COALESCE(s.metadata_enabled,1)=1")
    if stale_only:
        update_hours=max(1,_as_int(_setting("General","update_frequency","168"),168))
        where.append("(m.last_refresh IS NULL OR m.last_refresh<=datetime(CURRENT_TIMESTAMP,?))")
        params.append(f"-{update_hours} hours")
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    with cx() as c:
        rows = c.execute(f"""SELECT s.id,s.name FROM shows s
                            LEFT JOIN metadata_refresh_state m ON m.show_id=s.id
                            {where_sql}
                            ORDER BY s.name COLLATE NOCASE""", params).fetchall()
    return [(int(r["id"]), r["name"]) for r in rows]

def full_refresh_preview(include_paused=False, stale_only=False):
    tmdb = tmdb_status()
    rows = _eligible_show_ids(include_paused=include_paused, stale_only=stale_only)
    return {"ok": True, "tmdb": tmdb, "total": len(rows), "sample": [{"show_id": sid, "name": name} for sid, name in rows[:25]],
            "include_paused": bool(include_paused), "stale_only": bool(stale_only)}

def start_full_refresh(batch_size=10, include_paused=False, stale_only=False, delay_seconds=0.15):
    status = tmdb_status()
    if not status.get("configured"):
        raise tmdb_client.TMDBConfigurationError("TMDb is not configured. Add TMDB_BEARER_TOKEN or TMDB_API_KEY in .env before running a full-library metadata refresh.")
    rows = _eligible_show_ids(include_paused=include_paused, stale_only=stale_only)
    job_id = uuid.uuid4().hex[:12]
    batch_size=max(1,min(int(batch_size or 10),50))
    delay_seconds=max(0.0,min(float(delay_seconds or 0.15),3.0))
    _set_job(job_id, status="queued", stage="Queued", percent=0, total=len(rows), processed=0, succeeded=0,
             skipped=0, failed=0, current_show="", errors=[], created_at=datetime.now().isoformat(timespec="seconds"),
             batch_size=batch_size, include_paused=bool(include_paused), stale_only=bool(stale_only), tmdb=status)
    t=threading.Thread(target=_run_full_refresh_job, args=(job_id, rows, delay_seconds), daemon=True)
    t.start()
    return _job_snapshot(job_id)

def _run_full_refresh_job(job_id, rows, delay_seconds):
    total=len(rows)
    _set_job(job_id, status="running", stage="Refreshing metadata", percent=0, message="Starting full-library metadata refresh.")
    succeeded=skipped=failed=0
    errors=[]
    for idx, (show_id, name) in enumerate(rows, start=1):
        _set_job(job_id, processed=idx-1, current_show=name, percent=int(((idx-1)/total)*100) if total else 100,
                 message=f"Refreshing {name}")
        try:
            refresh_show(show_id)
            succeeded+=1
        except Exception as ex:
            failed+=1
            msg=str(ex)
            if len(errors) < 50:
                errors.append({"show_id":show_id,"name":name,"error":msg[:500]})
            with cx() as c:
                c.execute("""INSERT INTO metadata_refresh_state(show_id,last_status,last_error,updated_at)
                             VALUES(?,'Error',?,CURRENT_TIMESTAMP)
                             ON CONFLICT(show_id) DO UPDATE SET
                               last_status='Error',last_error=excluded.last_error,updated_at=CURRENT_TIMESTAMP""",
                          (show_id,msg[:1000]))
                c.commit()
        if delay_seconds:
            time.sleep(delay_seconds)
        _set_job(job_id, processed=idx, succeeded=succeeded, skipped=skipped, failed=failed,
                 percent=int((idx/total)*100) if total else 100, errors=errors)
    _set_job(job_id, status="complete", stage="Complete", percent=100, current_show="",
             message=f"Full metadata refresh complete. {succeeded} succeeded, {failed} failed.",
             completed_at=datetime.now().isoformat(timespec="seconds"), succeeded=succeeded, skipped=skipped, failed=failed, errors=errors)


# ---- v17.15 missing metadata, artwork and background job helpers ----

def _safe_bool(v, default=False):
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def missing_metadata_candidates(limit=200, include_paused=False):
    """Return shows that should be refreshed because IDs/art/episode data are missing."""
    limit=max(1,min(int(limit or 200),2000))
    where=["COALESCE(s.metadata_enabled,1)=1"]
    if not include_paused:
        where.append("COALESCE(s.paused,0)=0")
    where.append("""(
        COALESCE(s.overview,'')='' OR COALESCE(s.poster,'')='' OR
        (COALESCE(s.imdb_id,'')='' AND s.tmdb_id IS NULL AND s.tvdb_id IS NULL) OR
        m.show_id IS NULL OR COALESCE(m.last_status,'') IN ('','Error') OR
        EXISTS (SELECT 1 FROM episodes e WHERE e.show_id=s.id AND (COALESCE(e.name,'')='' OR COALESCE(e.airdate,'')='' OR COALESCE(e.still_url,'')=''))
    )""")
    sql=f"""SELECT s.id,s.name,s.tmdb_id,s.imdb_id,s.tvdb_id,s.poster,m.last_status,m.last_error,m.last_refresh
            FROM shows s LEFT JOIN metadata_refresh_state m ON m.show_id=s.id
            WHERE {' AND '.join(where)}
            ORDER BY CASE WHEN m.show_id IS NULL THEN 0 ELSE 1 END, s.name COLLATE NOCASE
            LIMIT ?"""
    with cx() as c:
        rows=[dict(r) for r in c.execute(sql,(limit,)).fetchall()]
    return rows


def missing_metadata_preview(limit=200, include_paused=False):
    rows=missing_metadata_candidates(limit=limit, include_paused=include_paused)
    return {"ok": True, "tmdb": tmdb_status(), "total": len(rows), "sample": rows[:25], "limit": limit, "include_paused": bool(include_paused)}


def refresh_missing_metadata(limit=200, include_paused=False, delay_seconds=0.15, progress_callback=None):
    status=tmdb_status()
    if not status.get("configured"):
        raise tmdb_client.TMDBConfigurationError("TMDb is not configured. Add TMDB_BEARER_TOKEN or TMDB_API_KEY before scheduling missing metadata refresh.")
    rows=missing_metadata_candidates(limit=limit, include_paused=include_paused)
    total=len(rows)
    succeeded=failed=skipped=0
    errors=[]
    for idx,row in enumerate(rows, start=1):
        if progress_callback:
            progress_callback({"total":total,"processed":idx-1,"succeeded":succeeded,"failed":failed,"skipped":skipped,"percent":int(((idx-1)/total)*100) if total else 100,"current_show":row.get("name"),"message":f"Refreshing missing metadata for {row.get('name')}"})
        try:
            refresh_show(row["id"])
            succeeded+=1
        except Exception as ex:
            failed+=1
            err={"show_id":row.get("id"),"name":row.get("name"),"error":str(ex)[:500]}
            errors.append(err)
            _record_refresh_error(row.get("id"), ex)
        if delay_seconds:
            time.sleep(max(0.0,min(float(delay_seconds),3.0)))
        if progress_callback:
            progress_callback({"total":total,"processed":idx,"succeeded":succeeded,"failed":failed,"skipped":skipped,"percent":int((idx/total)*100) if total else 100,"current_show":row.get("name"),"errors":errors[-25:]})
    return {"ok": True, "total": total, "processed": total, "succeeded": succeeded, "failed": failed, "skipped": skipped, "errors": errors[-50:]}


def start_missing_metadata_refresh(limit=200, include_paused=False, delay_seconds=0.15):
    def worker(job_id):
        job_center.update_job(job_id, stage="Missing metadata", message="Refreshing shows with missing IDs, descriptions, episode titles, dates or art.", percent=1)
        def progress(evt):
            updates={k:evt[k] for k in ("total","processed","succeeded","failed","skipped","percent","current_show","errors") if k in evt}
            updates["stage"]="Missing metadata"
            updates["message"]=evt.get("message") or "Refreshing missing metadata."
            job_center.update_job(job_id, **updates)
        result=refresh_missing_metadata(limit=limit, include_paused=include_paused, delay_seconds=delay_seconds, progress_callback=progress)
        job_center.update_job(job_id, status="complete", stage="Complete", message=f"Missing metadata refresh complete: {result['succeeded']} succeeded, {result['failed']} failed.", percent=100, result=result, processed=result["processed"], succeeded=result["succeeded"], failed=result["failed"], skipped=result["skipped"], errors=result.get("errors",[]))
        return result
    preview=missing_metadata_preview(limit=limit, include_paused=include_paused)
    return job_center.run_background("missing_metadata_refresh", worker, stage="Queued", message="Missing metadata refresh queued.", total=preview.get("total",0), meta={"include_paused": bool(include_paused), "limit": limit})


def artwork_candidates(limit=200, include_episodes=True):
    limit=max(1,min(int(limit or 200),2000))
    with cx() as c:
        show_rows=[dict(r) for r in c.execute("""SELECT id,name,poster,location FROM shows
                 WHERE COALESCE(metadata_enabled,1)=1 AND COALESCE(location,'')<>'' AND COALESCE(poster,'')<>''
                 ORDER BY name COLLATE NOCASE LIMIT ?""",(limit,)).fetchall()]
        episode_rows=[]
        if include_episodes:
            episode_rows=[dict(r) for r in c.execute("""SELECT e.id,e.show_id,e.season,e.episode,e.name,e.location,e.still_url,s.name show_name
                    FROM episodes e JOIN shows s ON s.id=e.show_id
                    WHERE COALESCE(e.location,'')<>'' AND COALESCE(e.still_url,'')<>'' AND COALESCE(e.still_path,'')=''
                    ORDER BY s.name COLLATE NOCASE,e.season,e.episode LIMIT ?""",(limit,)).fetchall()]
    return {"shows": show_rows, "episodes": episode_rows}


def artwork_preview(limit=200, include_episodes=True):
    cands=artwork_candidates(limit=limit, include_episodes=include_episodes)
    return {"ok": True, "show_art_candidates": len(cands["shows"]), "episode_art_candidates": len(cands["episodes"]), "sample_shows": cands["shows"][:10], "sample_episodes": cands["episodes"][:10]}


def _download_file(url, target):
    target=Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    r=requests.get(url, timeout=25, headers={"User-Agent":"TVManager/17.15"})
    r.raise_for_status()
    target.write_bytes(r.content)
    return target


def refresh_artwork(limit=200, include_episodes=True, progress_callback=None):
    cands=artwork_candidates(limit=limit, include_episodes=include_episodes)
    work=[]
    for s in cands["shows"]:
        root=Path(str(s.get("location") or ""))
        if root:
            work.append(("show", s, root / "poster.jpg", s.get("poster")))
    for e in cands["episodes"]:
        media=Path(str(e.get("location") or ""))
        if media:
            work.append(("episode", e, media.with_suffix(".jpg"), e.get("still_url")))
    total=len(work)
    succeeded=failed=skipped=0
    errors=[]
    for idx,(kind,row,target,url) in enumerate(work, start=1):
        label=(row.get("name") or row.get("show_name") or str(row.get("id")))
        if progress_callback:
            progress_callback({"total":total,"processed":idx-1,"succeeded":succeeded,"failed":failed,"skipped":skipped,"percent":int(((idx-1)/total)*100) if total else 100,"message":f"Saving {kind} art for {label}"})
        try:
            if not url:
                skipped+=1
                continue
            if kind=="episode" and target.exists():
                skipped+=1
                continue
            saved=_download_file(url,target)
            if kind=="episode":
                with cx() as c:
                    c.execute("UPDATE episodes SET still_path=?,metadata_updated_at=CURRENT_TIMESTAMP WHERE id=?",(str(saved),row["id"]))
                    c.commit()
            succeeded+=1
        except Exception as ex:
            failed+=1
            errors.append({"kind":kind,"id":row.get("id"),"name":label,"error":str(ex)[:500]})
        if progress_callback:
            progress_callback({"total":total,"processed":idx,"succeeded":succeeded,"failed":failed,"skipped":skipped,"percent":int((idx/total)*100) if total else 100,"errors":errors[-25:]})
    return {"ok": True, "total": total, "processed": total, "succeeded": succeeded, "failed": failed, "skipped": skipped, "errors": errors[-50:]}


def start_artwork_refresh(limit=200, include_episodes=True):
    def worker(job_id):
        def progress(evt):
            updates={k:evt[k] for k in ("total","processed","succeeded","failed","skipped","percent","errors") if k in evt}
            updates["stage"]="Artwork"
            updates["message"]=evt.get("message") or "Refreshing show and episode artwork."
            job_center.update_job(job_id, **updates)
        result=refresh_artwork(limit=limit, include_episodes=include_episodes, progress_callback=progress)
        job_center.update_job(job_id, status="complete", stage="Complete", message=f"Artwork refresh complete: {result['succeeded']} saved, {result['failed']} failed, {result['skipped']} skipped.", percent=100, result=result, processed=result["processed"], succeeded=result["succeeded"], failed=result["failed"], skipped=result["skipped"], errors=result.get("errors",[]))
        return result
    preview=artwork_preview(limit=limit, include_episodes=include_episodes)
    return job_center.run_background("artwork_refresh", worker, stage="Queued", message="Show and episode artwork refresh queued.", total=preview["show_art_candidates"]+preview["episode_art_candidates"], meta={"include_episodes": bool(include_episodes), "limit": limit})
