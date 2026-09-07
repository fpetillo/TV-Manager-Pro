from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import dbcore

SHOW_NAME_KEYS = ("show_name", "name", "showname", "title")
SHOW_ID_KEYS = ("indexer_id", "tvdb_id", "show_id", "indexerid")


def _pick(data: dict[str, Any], *names: str) -> Any:
    by_lower = {str(k).lower(): v for k, v in data.items()}
    for name in names:
        if name.lower() in by_lower:
            return by_lower[name.lower()]
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _imdb(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    if text.lower().startswith("tt"):
        suffix = text[2:]
        return f"tt{int(suffix):07d}" if suffix.isdigit() else text
    return f"tt{int(text):07d}" if text.isdigit() else text


def _normalize_status(value: Any, paused: Any = None) -> str:
    if _int(paused):
        return "Paused"
    raw = (_text(value) or "").lower()
    if raw in {"ended", "archived"}:
        return "Ended"
    if raw in {"paused", "ignored", "skip"}:
        return "Paused"
    return "Active"


def active_counts(db_path: str | Path) -> dict[str, Any]:
    db_path = Path(db_path)
    out: dict[str, Any] = {"database": str(db_path), "exists": db_path.exists()}
    if not db_path.exists():
        out.update({"shows": 0, "episodes": 0, "import_runs": 0, "imported_show_audit_rows": 0})
        return out
    with dbcore.connect(db_path, wal=False, readonly=True) as conn:
        def count(sql: str) -> int:
            try:
                return int(conn.execute(sql).fetchone()[0])
            except sqlite3.Error:
                return 0
        out.update({
            "shows": count("SELECT COUNT(*) FROM shows"),
            "episodes": count("SELECT COUNT(*) FROM episodes"),
            "import_runs": count("SELECT COUNT(*) FROM import_runs"),
            "imported_show_audit_rows": count("SELECT COUNT(*) FROM import_run_details WHERE item_type='show' AND action IN ('imported','skipped-existing')"),
        })
        try:
            last = conn.execute("SELECT * FROM import_runs ORDER BY id DESC LIMIT 1").fetchone()
            out["last_import_run"] = dict(last) if last else None
        except sqlite3.Error:
            out["last_import_run"] = None
    return out


def recover_shows_from_import_audit(db_path: str | Path) -> dict[str, Any]:
    """Rebuild missing show rows from import audit records if a prior import logged details but shows are absent.

    This is intentionally conservative: it only fills an empty shows table from item-level
    SickChill import audit rows. It never deletes existing records.
    """
    db_path = Path(db_path)
    report = {"attempted": False, "created": 0, "reason": ""}
    if not db_path.exists():
        report["reason"] = "database does not exist"
        return report
    with dbcore.connect(db_path, wal=False) as conn:
        try:
            show_count = int(conn.execute("SELECT COUNT(*) FROM shows").fetchone()[0])
            audit_count = int(conn.execute("SELECT COUNT(*) FROM import_run_details WHERE item_type='show'").fetchone()[0])
        except sqlite3.Error as exc:
            report["reason"] = f"schema not ready: {exc}"
            return report
        if show_count > 0:
            report["reason"] = "shows already present"
            return report
        if audit_count == 0:
            report["reason"] = "no show audit rows available"
            return report
        report["attempted"] = True
        rows = conn.execute("""
            SELECT source_name, source_id, tvmanager_id, action, message, details_json
            FROM import_run_details
            WHERE item_type='show'
            ORDER BY id
        """).fetchall()
        seen: set[str] = set()
        for row in rows:
            try:
                details = json.loads(row["details_json"] or "{}")
                if not isinstance(details, dict):
                    details = {}
            except Exception:
                details = {}
            name = _text(_pick(details, *SHOW_NAME_KEYS)) or _text(row["message"]) or "Unknown"
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            legacy_id = _int(row["source_id"]) or _int(_pick(details, *SHOW_ID_KEYS))
            tvdb_id = _int(_pick(details, "tvdb_id", "indexer_id", "indexerid")) or legacy_id
            imdb_id = _imdb(_pick(details, "imdb_id", "imdbid", "imdb"))
            cur = conn.execute(
                """INSERT INTO shows(imdb_id,tvdb_id,legacy_indexer_id,name,first_air_date,location,network,genre,quality,paused,anime,status,legacy_data)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    imdb_id,
                    tvdb_id,
                    legacy_id,
                    name,
                    _text(_pick(details, "startyear", "first_air_date", "firstaired")),
                    _text(_pick(details, "location", "path")),
                    _text(_pick(details, "network")),
                    _text(_pick(details, "genre", "genres")),
                    _text(_pick(details, "quality")),
                    _int(_pick(details, "paused")) or 0,
                    _int(_pick(details, "anime")) or 0,
                    _normalize_status(_pick(details, "status"), paused=_pick(details, "paused")),
                    json.dumps(details, default=str),
                ),
            )
            show_id = int(cur.lastrowid)
            if legacy_id is not None:
                conn.execute(
                    """INSERT OR REPLACE INTO legacy_identity_map(source_name, legacy_show_id, tvmanager_show_id, tvdb_id, imdb_id, show_name)
                       VALUES(?,?,?,?,?,?)""",
                    (row["source_name"] or "recovered-import", legacy_id, show_id, tvdb_id, imdb_id, name),
                )
            report["created"] += 1
        report["reason"] = "recovered shows from import audit" if report["created"] else "no recoverable show records"
    return report
