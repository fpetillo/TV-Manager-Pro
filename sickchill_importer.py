from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

import dbcore

SHOW_TABLE_CANDIDATES = ("tv_shows", "shows", "tvshows", "show")
EPISODE_TABLE_CANDIDATES = ("tv_episodes", "episodes", "tvepisodes", "episode")

SHOW_NAME_COLUMNS = ("show_name", "name", "showname", "title")
SHOW_ID_COLUMNS = ("indexer_id", "tvdb_id", "show_id", "indexerid")
EPISODE_SHOW_ID_COLUMNS = ("showid", "show_id", "indexer_id", "tvdb_id", "show_id_indexer")


def _connect_readonly(path: str | Path) -> sqlite3.Connection:
    return dbcore.connect(path, wal=False, readonly=True)


def _tables(conn: sqlite3.Connection) -> list[str]:
    return [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]


def _columns(conn: sqlite3.Connection, table: str | None) -> list[str]:
    if not table:
        return []
    return [r["name"] for r in conn.execute(f'PRAGMA table_info("{table}")')]


def _choose_table(tables: Iterable[str], candidates: Iterable[str]) -> str | None:
    by_lower = {t.lower(): t for t in tables}
    for name in candidates:
        if name in by_lower:
            return by_lower[name]
    return None


def detect_schema(path: str | Path) -> dict[str, Any]:
    """Detect the usable SickChill/SickBeard table layout without modifying either database."""
    with _connect_readonly(path) as conn:
        tables = _tables(conn)
        show_table = _choose_table(tables, SHOW_TABLE_CANDIDATES)
        episode_table = _choose_table(tables, EPISODE_TABLE_CANDIDATES)
        show_columns = _columns(conn, show_table)
        episode_columns = _columns(conn, episode_table)
        return {
            "tables": tables,
            "show_table": show_table,
            "episode_table": episode_table,
            "show_columns": show_columns,
            "episode_columns": episode_columns,
            "recognized": bool(show_table),
            "warnings": _schema_warnings(show_table, episode_table, show_columns, episode_columns),
        }


def _schema_warnings(show_table: str | None, episode_table: str | None, show_cols: list[str], ep_cols: list[str]) -> list[str]:
    warnings: list[str] = []
    lower_show = {c.lower() for c in show_cols}
    lower_ep = {c.lower() for c in ep_cols}
    if not show_table:
        warnings.append("No recognizable SickChill show table was found.")
    elif not any(c in lower_show for c in SHOW_NAME_COLUMNS):
        warnings.append("Show table found, but no common show-name column was detected.")
    if not episode_table:
        warnings.append("No episode table was found; only shows can be imported.")
    elif not {"season", "episode"}.issubset(lower_ep):
        warnings.append("Episode table found, but season/episode columns are incomplete.")
    return warnings


def _pick(row: sqlite3.Row, *names: str) -> Any:
    keys = {k.lower(): k for k in row.keys()}
    for name in names:
        key = keys.get(name.lower())
        if key is not None:
            return row[key]
    return None


def _int_or_none(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def normalize_imdb_id(value: Any) -> str | None:
    text = _text_or_none(value)
    if not text:
        return None
    if text.lower().startswith("tt"):
        suffix = text[2:]
        if suffix.isdigit():
            return f"tt{int(suffix):07d}"
        return text
    if text.isdigit():
        return f"tt{int(text):07d}"
    return text


def normalize_status(value: Any, *, paused: Any = None) -> str:
    if _int_or_none(paused):
        return "Paused"
    raw = (_text_or_none(value) or "").lower()
    if raw in {"", "unknown", "none"}:
        return "Active"
    if raw in {"ended", "archived"}:
        return "Ended"
    if raw in {"paused", "ignored", "skip"}:
        return "Paused"
    return "Active"


def _existing_show(conn: sqlite3.Connection, *, imdb_id=None, tvdb_id=None, legacy_id=None, name=None) -> int | None:
    for column, value in (("imdb_id", imdb_id), ("tvdb_id", tvdb_id), ("legacy_indexer_id", legacy_id)):
        if value not in (None, ""):
            row = conn.execute(f"SELECT id FROM shows WHERE {column}=? LIMIT 1", (value,)).fetchone()
            if row:
                return int(row["id"])
    if name:
        row = conn.execute("SELECT id FROM shows WHERE lower(name)=lower(?) LIMIT 1", (name,)).fetchone()
        if row:
            return int(row["id"])
    return None


def _source_show_identity(row: sqlite3.Row) -> dict[str, Any]:
    legacy_id = _int_or_none(_pick(row, *SHOW_ID_COLUMNS))
    tvdb_id = _int_or_none(_pick(row, "tvdb_id", "indexer_id", "indexerid"))
    return {
        "legacy_id": legacy_id,
        "tvdb_id": tvdb_id,
        "imdb_id": normalize_imdb_id(_pick(row, "imdb_id", "imdbid", "imdb")),
        "name": _text_or_none(_pick(row, *SHOW_NAME_COLUMNS)) or "Unknown",
    }


def analyze_database(source_db: str | Path, target_db: str | Path | None = None) -> dict[str, Any]:
    """Return a no-write migration preview for a SickChill database."""
    source_db = Path(source_db)
    schema = detect_schema(source_db)
    summary: dict[str, Any] = {
        "source": str(source_db),
        "schema": schema,
        "shows_found": 0,
        "episodes_found": 0,
        "shows_matching_existing": 0,
        "shows_ready_to_import": 0,
        "sample_shows": [],
        "ready": False,
    }
    if not schema["show_table"]:
        return summary

    with _connect_readonly(source_db) as src:
        show_rows = src.execute(f'SELECT * FROM "{schema["show_table"]}"').fetchall()
        summary["shows_found"] = len(show_rows)
        if schema["episode_table"]:
            summary["episodes_found"] = src.execute(f'SELECT COUNT(*) n FROM "{schema["episode_table"]}"').fetchone()["n"]

        existing_ids: set[int] = set()
        if target_db:
            with dbcore.connect(target_db, wal=False, readonly=True) as dst:
                for row in show_rows:
                    ident = _source_show_identity(row)
                    match = _existing_show(dst, imdb_id=ident["imdb_id"], tvdb_id=ident["tvdb_id"], legacy_id=ident["legacy_id"], name=ident["name"])
                    if match:
                        existing_ids.add(match)
        summary["shows_matching_existing"] = len(existing_ids)
        summary["shows_ready_to_import"] = max(0, summary["shows_found"] - len(existing_ids))
        for row in show_rows[:10]:
            ident = _source_show_identity(row)
            summary["sample_shows"].append(ident)
        summary["ready"] = bool(summary["shows_found"])
    return summary


def ensure_v17_import_tables(target_db: str | Path) -> None:
    with dbcore.connect(target_db) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS legacy_identity_map(
              source_name TEXT NOT NULL,
              legacy_show_id INTEGER,
              tvmanager_show_id INTEGER NOT NULL,
              tvdb_id INTEGER,
              imdb_id TEXT,
              show_name TEXT,
              imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY(source_name, legacy_show_id)
            );
            CREATE TABLE IF NOT EXISTS import_run_details(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              import_run_id INTEGER,
              source_name TEXT NOT NULL,
              item_type TEXT NOT NULL,
              source_id TEXT,
              tvmanager_id INTEGER,
              action TEXT NOT NULL,
              message TEXT,
              details_json TEXT,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def import_database(source_db: str | Path, target_db: str | Path, source_name: str | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    """Import shows and episodes from a SickChill SQLite database.

    The importer is idempotent: repeat runs map to existing shows by IMDb, TVDb,
    legacy indexer ID, or normalized show name and skip duplicate episode rows.
    """
    source_db = Path(source_db)
    target_db = Path(target_db)
    source_name = source_name or source_db.name
    schema = detect_schema(source_db)
    if not schema["show_table"]:
        raise ValueError("No recognizable SickChill show table found. Tables: " + ", ".join(schema["tables"]))

    ensure_v17_import_tables(target_db)
    stats = {
        "source_name": source_name,
        "dry_run": dry_run,
        "shows_found": 0,
        "shows_imported": 0,
        "shows_skipped": 0,
        "episodes_found": 0,
        "episodes_imported": 0,
        "episodes_skipped": 0,
        "details": [],
        "schema": schema,
    }

    src = _connect_readonly(source_db)
    dst = dbcore.connect(target_db)
    mapping: dict[int, int] = {}
    import_run_id: int | None = None
    try:
        show_rows = src.execute(f'SELECT * FROM "{schema["show_table"]}"').fetchall()
        stats["shows_found"] = len(show_rows)
        if not dry_run:
            run_cur = dst.execute(
                """INSERT INTO import_runs(source_name, shows_found, episodes_found)
                   VALUES(?,?,?)""",
                (source_name, stats["shows_found"], 0),
            )
            import_run_id = int(run_cur.lastrowid)

        for row in show_rows:
            ident = _source_show_identity(row)
            legacy_id = ident["legacy_id"]
            tvdb_id = ident["tvdb_id"]
            imdb_id = ident["imdb_id"]
            name = ident["name"]
            existing_id = _existing_show(dst, imdb_id=imdb_id, tvdb_id=tvdb_id, legacy_id=legacy_id, name=name)
            action = "skipped-existing" if existing_id else "imported"
            if existing_id:
                show_id = existing_id
                stats["shows_skipped"] += 1
            else:
                stats["shows_imported"] += 1
                if dry_run:
                    show_id = -stats["shows_imported"]
                else:
                    cur = dst.execute(
                        """INSERT INTO shows(imdb_id,tvdb_id,legacy_indexer_id,name,first_air_date,location,network,genre,quality,paused,anime,status,legacy_data)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            imdb_id,
                            tvdb_id,
                            legacy_id,
                            name,
                            _text_or_none(_pick(row, "startyear", "first_air_date", "firstaired")),
                            _text_or_none(_pick(row, "location", "path")),
                            _text_or_none(_pick(row, "network")),
                            _text_or_none(_pick(row, "genre", "genres")),
                            _text_or_none(_pick(row, "quality")),
                            _int_or_none(_pick(row, "paused")) or 0,
                            _int_or_none(_pick(row, "anime")) or 0,
                            normalize_status(_pick(row, "status"), paused=_pick(row, "paused")),
                            json.dumps(dict(row), default=str),
                        ),
                    )
                    show_id = int(cur.lastrowid)
            if legacy_id is not None:
                mapping[legacy_id] = show_id
                if not dry_run and show_id > 0:
                    dst.execute(
                        """INSERT OR REPLACE INTO legacy_identity_map(source_name, legacy_show_id, tvmanager_show_id, tvdb_id, imdb_id, show_name)
                           VALUES(?,?,?,?,?,?)""",
                        (source_name, legacy_id, show_id, tvdb_id, imdb_id, name),
                    )
            _record_detail(dst, stats, import_run_id, source_name, "show", legacy_id, show_id, action, name, dict(row), dry_run)

        if schema["episode_table"]:
            episode_rows = src.execute(f'SELECT * FROM "{schema["episode_table"]}"').fetchall()
            stats["episodes_found"] = len(episode_rows)
            for row in episode_rows:
                legacy_show_id = _int_or_none(_pick(row, *EPISODE_SHOW_ID_COLUMNS))
                show_id = mapping.get(legacy_show_id) if legacy_show_id is not None else None
                if not show_id and legacy_show_id is not None:
                    show_id = _existing_show(dst, tvdb_id=legacy_show_id, legacy_id=legacy_show_id)
                season = _int_or_none(_pick(row, "season"))
                episode = _int_or_none(_pick(row, "episode"))
                if not show_id or season is None or episode is None:
                    stats["episodes_skipped"] += 1
                    _record_detail(dst, stats, import_run_id, source_name, "episode", legacy_show_id, show_id, "skipped-unmatched", "Missing show/season/episode identity", dict(row), dry_run)
                    continue
                exists = dst.execute("SELECT id FROM episodes WHERE show_id=? AND season=? AND episode=?", (show_id, season, episode)).fetchone()
                if exists:
                    stats["episodes_skipped"] += 1
                    _record_detail(dst, stats, import_run_id, source_name, "episode", f"{legacy_show_id}:{season}x{episode}", int(exists["id"]), "skipped-existing", "Episode already exists", dict(row), dry_run)
                    continue
                stats["episodes_imported"] += 1
                if dry_run:
                    episode_id = -stats["episodes_imported"]
                else:
                    cur = dst.execute(
                        """INSERT INTO episodes(show_id,season,episode,name,airdate,status,location,file_size,release_name,quality,legacy_data)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            show_id,
                            season,
                            episode,
                            _text_or_none(_pick(row, "name", "episode_name")),
                            _text_or_none(_pick(row, "airdate", "firstaired")),
                            _text_or_none(_pick(row, "status")),
                            _text_or_none(_pick(row, "location", "file_path")),
                            _int_or_none(_pick(row, "file_size", "filesize", "size")),
                            _text_or_none(_pick(row, "release_name", "release", "scene_release")),
                            _text_or_none(_pick(row, "quality")),
                            json.dumps(dict(row), default=str),
                        ),
                    )
                    episode_id = int(cur.lastrowid)
                _record_detail(dst, stats, import_run_id, source_name, "episode", f"{legacy_show_id}:{season}x{episode}", episode_id, "imported", "Episode imported", dict(row), dry_run)

        if not dry_run and import_run_id:
            dst.execute(
                """UPDATE import_runs SET shows_imported=?, shows_skipped=?, episodes_found=?, episodes_imported=?, episodes_skipped=? WHERE id=?""",
                (stats["shows_imported"], stats["shows_skipped"], stats["episodes_found"], stats["episodes_imported"], stats["episodes_skipped"], import_run_id),
            )
            dst.commit()
        elif dry_run:
            dst.rollback()
    finally:
        src.close()
        dst.close()
    return stats


def _record_detail(conn, stats, import_run_id, source_name, item_type, source_id, tvmanager_id, action, message, details, dry_run):
    item = {
        "item_type": item_type,
        "source_id": None if source_id is None else str(source_id),
        "tvmanager_id": tvmanager_id,
        "action": action,
        "message": message,
    }
    if len(stats["details"]) < 200:
        stats["details"].append(item)
    if not dry_run:
        conn.execute(
            """INSERT INTO import_run_details(import_run_id,source_name,item_type,source_id,tvmanager_id,action,message,details_json)
               VALUES(?,?,?,?,?,?,?,?)""",
            (import_run_id, source_name, item_type, None if source_id is None else str(source_id), tvmanager_id if isinstance(tvmanager_id, int) and tvmanager_id > 0 else None, action, message, json.dumps(details, default=str)),
        )
