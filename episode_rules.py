from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import dbcore

IGNORE_STATUS = "Ignored"


def cx(db_path: Path | str):
    return dbcore.connect(Path(db_path), wal=False)


def init(db_path: Path | str) -> None:
    """Install episode-level management columns and history tables."""
    with cx(db_path) as c:
        ecols = {r["name"] for r in c.execute("PRAGMA table_info(episodes)").fetchall()}
        for name, definition in {
            "monitored": "INTEGER DEFAULT 1",
            "ignored": "INTEGER DEFAULT 0",
            "ignored_reason": "TEXT",
            "ignored_at": "TEXT",
            "ignored_source": "TEXT",
            "managed_note": "TEXT",
        }.items():
            if name not in ecols:
                c.execute(f'ALTER TABLE episodes ADD COLUMN "{name}" {definition}')
        c.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_episodes_ignored ON episodes(ignored);
            CREATE INDEX IF NOT EXISTS idx_episodes_show_ignored ON episodes(show_id, ignored);
            CREATE TABLE IF NOT EXISTS episode_management_history(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              show_id INTEGER,
              action TEXT NOT NULL,
              filter_json TEXT,
              affected INTEGER DEFAULT 0,
              message TEXT,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        c.commit()


def considered_sql(alias: str = "e", include_ignored: bool = False, ignore_specials: bool = False) -> str:
    parts: list[str] = []
    if not include_ignored:
        parts.append(f"COALESCE({alias}.ignored,0)=0")
        parts.append(f"lower(COALESCE({alias}.status,''))<>'ignored'")
    if ignore_specials:
        parts.append(f"COALESCE({alias}.season,-1)<>0")
    return (" AND " + " AND ".join(parts)) if parts else ""


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _as_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except Exception:
        return default


def _filter(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    where = ["1=1"]
    params: list[Any] = []
    if filters.get("show_id"):
        where.append("e.show_id=?")
        params.append(_as_int(filters.get("show_id")))
    if filters.get("season") not in (None, "", "all"):
        where.append("e.season=?")
        params.append(_as_int(filters.get("season")))
    if filters.get("specials") in (True, "1", "true", "yes", "on"):
        where.append("e.season=0")
    if filters.get("status") not in (None, "", "all"):
        where.append("lower(COALESCE(e.status,''))=lower(?)")
        params.append(str(filters.get("status")))
    if filters.get("from_status") not in (None, "", "all"):
        where.append("lower(COALESCE(e.status,''))=lower(?)")
        params.append(str(filters.get("from_status")))
    if filters.get("only_missing") in (True, "1", "true", "yes", 1):
        where.append("(e.location IS NULL OR trim(e.location)='')")
    if filters.get("only_downloaded") in (True, "1", "true", "yes", 1):
        where.append("e.location IS NOT NULL AND trim(e.location)<>''")
    if filters.get("only_aired") in (True, "1", "true", "yes", 1):
        where.append("(e.airdate IS NULL OR e.airdate<=date('now'))")
    if filters.get("ignored") not in (None, "", "all"):
        where.append("COALESCE(e.ignored,0)=?")
        params.append(1 if _truthy(filters.get("ignored")) else 0)
    if filters.get("monitored") not in (None, "", "all"):
        where.append("COALESCE(e.monitored,1)=?")
        params.append(1 if _truthy(filters.get("monitored")) else 0)
    ids = filters.get("episode_ids") or filters.get("ids")
    if ids:
        clean = [_as_int(x) for x in ids if _as_int(x) is not None]
        if clean:
            where.append("e.id IN (" + ",".join("?" for _ in clean) + ")")
            params.extend(clean)
    q = str(filters.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        where.append("(COALESCE(s.name,'') LIKE ? COLLATE NOCASE OR COALESCE(e.name,'') LIKE ? COLLATE NOCASE OR COALESCE(e.location,'') LIKE ? COLLATE NOCASE)")
        params.extend([like, like, like])
    return " AND ".join(where), params


def preview(db_path: Path | str, filters: dict[str, Any], sample_limit: int = 50) -> dict[str, Any]:
    init(db_path)
    where, params = _filter(filters or {})
    with cx(db_path) as c:
        total = int(c.execute(f"SELECT COUNT(*) FROM episodes e JOIN shows s ON s.id=e.show_id WHERE {where}", params).fetchone()[0])
        by_status = [dict(r) for r in c.execute(
            f"SELECT COALESCE(e.status,'') status, COALESCE(e.ignored,0) ignored, COUNT(*) count FROM episodes e JOIN shows s ON s.id=e.show_id WHERE {where} GROUP BY COALESCE(e.status,''), COALESCE(e.ignored,0) ORDER BY count DESC",
            params,
        ).fetchall()]
        sample = [dict(r) for r in c.execute(
            f"""
            SELECT e.id, e.show_id, s.name show_name, e.season, e.episode, e.name,
                   e.airdate, e.status, e.monitored, COALESCE(e.ignored,0) ignored,
                   e.ignored_reason, e.location
              FROM episodes e JOIN shows s ON s.id=e.show_id
             WHERE {where}
             ORDER BY s.name COLLATE NOCASE, e.season, e.episode
             LIMIT ?
            """,
            params + [max(1, min(int(sample_limit or 50), 500))],
        ).fetchall()]
    return {"total": total, "by_status": by_status, "sample": sample}


def apply(db_path: Path | str, filters: dict[str, Any], action: str, *, status: str | None = None,
          monitored: Any = None, ignored: Any = None, reason: str = "", note: str = "") -> dict[str, Any]:
    init(db_path)
    action = (action or "bulk_update").strip() or "bulk_update"
    filters = filters or {}
    where, params = _filter(filters)
    fields: list[str] = []
    vals: list[Any] = []
    msg_parts: list[str] = []
    now = datetime.now().replace(microsecond=0).isoformat()

    if status is not None and str(status).strip():
        fields.append("status=?"); vals.append(str(status).strip()); msg_parts.append(f"status={str(status).strip()}")
    if monitored is not None:
        fields.append("monitored=?"); vals.append(1 if _truthy(monitored) else 0); msg_parts.append("monitored" if _truthy(monitored) else "unmonitored")
    if ignored is not None:
        is_ignored = 1 if _truthy(ignored) else 0
        fields.append("ignored=?"); vals.append(is_ignored)
        fields.append("ignored_reason=?"); vals.append((reason or "Manual ignore" if is_ignored else "").strip())
        fields.append("ignored_at=?"); vals.append(now if is_ignored else None)
        fields.append("ignored_source=?"); vals.append(action if is_ignored else None)
        msg_parts.append("ignored" if is_ignored else "included")
        if is_ignored and status is None:
            fields.append("status=?"); vals.append(IGNORE_STATUS)
        elif not is_ignored and status is None:
            # Keep downloaded episodes downloaded; otherwise rejoin wanted workflow.
            fields.append("status=CASE WHEN location IS NOT NULL AND trim(location)<>'' THEN 'Downloaded' ELSE 'Wanted' END")
    if note:
        fields.append("managed_note=?"); vals.append(str(note))
    if not fields:
        raise ValueError("No episode-management change requested.")

    vals.extend(params)
    with cx(db_path) as c:
        cur = c.execute(
            f"UPDATE episodes SET {', '.join(fields)} WHERE id IN (SELECT e.id FROM episodes e JOIN shows s ON s.id=e.show_id WHERE {where})",
            vals,
        )
        affected = cur.rowcount if cur.rowcount is not None else 0
        c.execute(
            "INSERT INTO episode_management_history(show_id,action,filter_json,affected,message) VALUES(?,?,?,?,?)",
            (_as_int(filters.get("show_id")), action, json.dumps(filters, default=str), affected, ", ".join(msg_parts) or action),
        )
        try:
            c.execute(
                "INSERT INTO mass_update_history(action,filter_json,affected,message) VALUES(?,?,?,?)",
                (action, json.dumps(filters, default=str), affected, ", ".join(msg_parts) or action),
            )
        except Exception:
            pass
        c.commit()
    return {"ok": True, "affected": affected, "action": action, "message": ", ".join(msg_parts) or action}


def ignore_specials(db_path: Path | str, show_id: int | None = None, reason: str = "Season 00 / Specials excluded from wanted counts") -> dict[str, Any]:
    filters: dict[str, Any] = {"specials": True}
    if show_id:
        filters["show_id"] = show_id
    return apply(db_path, filters, "ignore_specials", ignored=True, monitored=False, reason=reason)


def include_specials(db_path: Path | str, show_id: int | None = None) -> dict[str, Any]:
    filters: dict[str, Any] = {"specials": True, "ignored": True}
    if show_id:
        filters["show_id"] = show_id
    return apply(db_path, filters, "include_specials", ignored=False, monitored=True)
