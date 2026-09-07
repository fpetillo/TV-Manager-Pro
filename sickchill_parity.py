"""SickChill parity utilities for TV Manager.

This module keeps the old SickChill "Manage" surfaces close together:
backlog overview, episode status management, failed download blacklist,
missed subtitle management and scene exceptions.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import dbcore


def cx(db_path: Path | str):
    return dbcore.connect(Path(db_path), wal=False)


def init(db_path: Path | str) -> None:
    with cx(db_path) as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS scene_exceptions(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              show_id INTEGER NOT NULL,
              exception_name TEXT NOT NULL,
              source TEXT DEFAULT 'manual',
              notes TEXT,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(show_id, exception_name)
            );
            CREATE INDEX IF NOT EXISTS idx_scene_exceptions_show ON scene_exceptions(show_id);

            CREATE TABLE IF NOT EXISTS mass_update_history(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              action TEXT NOT NULL,
              filter_json TEXT,
              affected INTEGER DEFAULT 0,
              message TEXT,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        c.commit()


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def summary(db_path: Path | str) -> dict[str, Any]:
    with cx(db_path) as c:
        counts = dict(c.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM shows) AS shows,
              (SELECT COUNT(*) FROM episodes) AS episodes,
              (SELECT COUNT(*) FROM episodes WHERE lower(COALESCE(status,'')) IN ('wanted','failed')
                 AND (location IS NULL OR trim(location)='')
                 AND (airdate IS NULL OR airdate<=date('now'))
                 AND COALESCE(monitored,1)=1) AS wanted,
              (SELECT COUNT(*) FROM failed_releases) AS failed_releases,
              (SELECT COUNT(*) FROM scene_exceptions) AS scene_exceptions,
              (SELECT COUNT(*) FROM episodes WHERE location IS NOT NULL AND trim(location)<>''
                 AND lower(COALESCE(subtitle_status,''))='missing') AS missed_subtitles,
              (SELECT COUNT(*) FROM episodes WHERE lower(COALESCE(status,''))='snatched') AS snatched,
              (SELECT COUNT(*) FROM downloads WHERE lower(COALESCE(status,'')) IN ('queued','downloading')) AS active_downloads
            """
        ).fetchone())
    return {
        "counts": counts,
        "features": [
            {"name": "Backlog overview", "status": "available", "detail": "Wanted/failed aired episodes grouped by show."},
            {"name": "Manage searches", "status": "available", "detail": "Run recent or backlog searches as background jobs."},
            {"name": "Episode status management", "status": "available", "detail": "Preview and mass-update selected episode status values."},
            {"name": "Failed downloads", "status": "available", "detail": "Review and blacklist failed releases so they are not grabbed again."},
            {"name": "Missed subtitle management", "status": "available", "detail": "Review downloaded episodes with missing subtitle status."},
            {"name": "Scene exceptions", "status": "available", "detail": "Add alternate show names used by release/indexer sites."},
            {"name": "Scheduler", "status": "available", "detail": "Recent search, backlog, metadata, artwork and maintenance jobs."},
            {"name": "History/logs", "status": "available", "detail": "Activity, acquisitions and scheduler history are retained."},
        ],
    }


def backlog_overview(db_path: Path | str, limit: int = 500) -> dict[str, Any]:
    limit = max(1, min(_as_int(limit, 500), 2000))
    with cx(db_path) as c:
        rows = c.execute(
            """
            SELECT s.id AS show_id, s.name AS show_name, s.network, s.quality, s.paused,
                   SUM(CASE WHEN lower(COALESCE(e.status,''))='wanted' THEN 1 ELSE 0 END) AS wanted,
                   SUM(CASE WHEN lower(COALESCE(e.status,''))='failed' THEN 1 ELSE 0 END) AS failed,
                   COUNT(*) AS total_missing,
                   MIN(COALESCE(e.airdate,'')) AS oldest_airdate,
                   MAX(COALESCE(e.airdate,'')) AS newest_airdate
              FROM episodes e
              JOIN shows s ON s.id=e.show_id
             WHERE lower(COALESCE(e.status,'')) IN ('wanted','failed')
               AND (e.location IS NULL OR trim(e.location)='')
               AND (e.airdate IS NULL OR e.airdate<=date('now'))
               AND COALESCE(e.monitored,1)=1
             GROUP BY s.id, s.name, s.network, s.quality, s.paused
             ORDER BY total_missing DESC, s.name COLLATE NOCASE
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return {"results": [dict(r) for r in rows], "count": len(rows), "limit": limit}


def status_preview(db_path: Path | str, filters: dict[str, Any]) -> dict[str, Any]:
    where, params = _status_filter(filters)
    with cx(db_path) as c:
        total = int(c.execute(f"SELECT COUNT(*) FROM episodes e JOIN shows s ON s.id=e.show_id WHERE {where}", params).fetchone()[0])
        by_status = [dict(r) for r in c.execute(
            f"SELECT COALESCE(e.status,'') status, COUNT(*) count FROM episodes e JOIN shows s ON s.id=e.show_id WHERE {where} GROUP BY COALESCE(e.status,'') ORDER BY count DESC",
            params,
        ).fetchall()]
        sample = [dict(r) for r in c.execute(
            f"""
            SELECT e.id, s.name show_name, e.season, e.episode, e.name, e.airdate, e.status, e.monitored
              FROM episodes e JOIN shows s ON s.id=e.show_id
             WHERE {where}
             ORDER BY s.name COLLATE NOCASE, e.season, e.episode
             LIMIT 25
            """,
            params,
        ).fetchall()]
    return {"total": total, "by_status": by_status, "sample": sample}


def status_apply(db_path: Path | str, filters: dict[str, Any], new_status: str, monitored: Any = None) -> dict[str, Any]:
    new_status = (new_status or "").strip()
    if not new_status:
        raise ValueError("New episode status is required.")
    where, params = _status_filter(filters)
    fields = ["status=?"]
    vals: list[Any] = [new_status]
    if monitored is not None:
        fields.append("monitored=?")
        vals.append(1 if bool(monitored) else 0)
    vals.extend(params)
    with cx(db_path) as c:
        cur = c.execute(
            f"UPDATE episodes SET {', '.join(fields)} WHERE id IN (SELECT e.id FROM episodes e JOIN shows s ON s.id=e.show_id WHERE {where})",
            vals,
        )
        affected = cur.rowcount if cur.rowcount is not None else 0
        c.execute(
            "INSERT INTO mass_update_history(action,filter_json,affected,message) VALUES(?,?,?,?)",
            ("episode_status", json.dumps(filters, default=str), affected, f"Set status to {new_status}"),
        )
        c.commit()
    return {"ok": True, "affected": affected, "status": new_status}


def _status_filter(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    where = ["1=1"]
    params: list[Any] = []
    if filters.get("show_id"):
        where.append("s.id=?")
        params.append(_as_int(filters.get("show_id")))
    if filters.get("season") not in (None, "", "all"):
        where.append("e.season=?")
        params.append(_as_int(filters.get("season")))
    if filters.get("from_status"):
        where.append("lower(COALESCE(e.status,''))=lower(?)")
        params.append(str(filters.get("from_status")))
    if filters.get("only_aired") in (True, "1", "true", "yes", 1):
        where.append("(e.airdate IS NULL OR e.airdate<=date('now'))")
    if filters.get("only_missing") in (True, "1", "true", "yes", 1):
        where.append("(e.location IS NULL OR trim(e.location)='')")
    if filters.get("monitored") not in (None, "", "all"):
        where.append("COALESCE(e.monitored,1)=?")
        params.append(1 if str(filters.get("monitored")).lower() in {"1", "true", "yes", "on"} else 0)
    return " AND ".join(where), params


def failed_downloads(db_path: Path | str, limit: int = 500) -> dict[str, Any]:
    limit = max(1, min(_as_int(limit, 500), 2000))
    with cx(db_path) as c:
        rows = c.execute("SELECT * FROM failed_releases ORDER BY failed_at DESC, id DESC LIMIT ?", (limit,)).fetchall()
    return {"results": [dict(r) for r in rows], "count": len(rows), "limit": limit}


def add_failed_download(db_path: Path | str, title: str, guid: str = "", reason: str = "Manual blacklist") -> dict[str, Any]:
    title = (title or "").strip()
    guid = (guid or title).strip()
    if not title and not guid:
        raise ValueError("Title or GUID is required.")
    with cx(db_path) as c:
        c.execute(
            "INSERT OR IGNORE INTO failed_releases(guid,title,reason) VALUES(?,?,?)",
            (guid, title or guid, reason or "Manual blacklist"),
        )
        c.commit()
    return {"ok": True, "guid": guid, "title": title or guid}


def remove_failed_download(db_path: Path | str, failed_id: int) -> dict[str, Any]:
    with cx(db_path) as c:
        cur = c.execute("DELETE FROM failed_releases WHERE id=?", (_as_int(failed_id),))
        c.commit()
    return {"ok": True, "deleted": cur.rowcount or 0}


def missed_subtitles(db_path: Path | str, limit: int = 500) -> dict[str, Any]:
    limit = max(1, min(_as_int(limit, 500), 2000))
    with cx(db_path) as c:
        rows = c.execute(
            """
            SELECT e.id AS episode_id, s.id AS show_id, s.name AS show_name, e.season, e.episode,
                   e.name, e.airdate, e.location, COALESCE(e.subtitle_status,'Unknown') subtitle_status
              FROM episodes e JOIN shows s ON s.id=e.show_id
             WHERE e.location IS NOT NULL AND trim(e.location)<>''
               AND lower(COALESCE(e.subtitle_status,'')) IN ('missing','unknown','')
             ORDER BY s.name COLLATE NOCASE, e.season, e.episode
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return {"results": [dict(r) for r in rows], "count": len(rows), "limit": limit}


def scene_exceptions(db_path: Path | str, show_id: int | None = None) -> dict[str, Any]:
    sql = """
        SELECT x.*, s.name AS show_name
          FROM scene_exceptions x JOIN shows s ON s.id=x.show_id
    """
    params: list[Any] = []
    if show_id:
        sql += " WHERE x.show_id=?"
        params.append(show_id)
    sql += " ORDER BY s.name COLLATE NOCASE, x.exception_name COLLATE NOCASE"
    with cx(db_path) as c:
        rows = c.execute(sql, params).fetchall()
    return {"results": [dict(r) for r in rows], "count": len(rows)}


def add_scene_exception(db_path: Path | str, show_id: int, exception_name: str, notes: str = "", source: str = "manual") -> dict[str, Any]:
    exception_name = (exception_name or "").strip()
    if not show_id or not exception_name:
        raise ValueError("Show and exception name are required.")
    with cx(db_path) as c:
        show = c.execute("SELECT id,name FROM shows WHERE id=?", (_as_int(show_id),)).fetchone()
        if not show:
            raise ValueError("Show not found.")
        c.execute(
            "INSERT OR IGNORE INTO scene_exceptions(show_id,exception_name,notes,source) VALUES(?,?,?,?)",
            (_as_int(show_id), exception_name, notes or "", source or "manual"),
        )
        c.commit()
    return {"ok": True, "show_id": _as_int(show_id), "exception_name": exception_name}


def remove_scene_exception(db_path: Path | str, exception_id: int) -> dict[str, Any]:
    with cx(db_path) as c:
        cur = c.execute("DELETE FROM scene_exceptions WHERE id=?", (_as_int(exception_id),))
        c.commit()
    return {"ok": True, "deleted": cur.rowcount or 0}
