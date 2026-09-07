from __future__ import annotations

from pathlib import Path
from typing import Any

import dbcore


def _tables(conn) -> set[str]:
    return {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _columns(conn, table: str) -> set[str]:
    if table not in _tables(conn):
        return set()
    return {r["name"] for r in conn.execute(f'PRAGMA table_info("{table}")')}


def _has_columns(conn, table: str, *names: str) -> bool:
    cols = _columns(conn, table)
    return all(name in cols for name in names)


def _count(conn, sql: str, params: tuple = ()) -> int:
    try:
        row = conn.execute(sql, params).fetchone()
        return int(row[0] if row else 0)
    except Exception:
        return 0


def _dict_rows(conn, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    except Exception:
        return []


def duplicate_candidates(db_path: str | Path, *, limit: int = 100) -> list[dict[str, Any]]:
    """Return likely duplicate media files from the v15+ fingerprint cache.

    The health page must work against new databases, partially migrated databases,
    and old SickChill-imported databases. This function therefore checks schema
    availability before using joins or optional columns.
    """
    with dbcore.connect(db_path, wal=False, readonly=True) as conn:
        tables = _tables(conn)
        if "media_fingerprints" not in tables:
            return []
        mf_cols = _columns(conn, "media_fingerprints")
        if not {"fingerprint", "file_size", "path"}.issubset(mf_cols):
            return []
        can_join_episode = "episodes" in tables and "episode_id" in mf_cols and _has_columns(conn, "episodes", "id", "show_id", "season", "episode")
        can_join_show = can_join_episode and "shows" in tables and _has_columns(conn, "shows", "id", "name")
        if can_join_episode and can_join_show:
            sql = """
                SELECT mf.fingerprint, mf.file_size, COUNT(*) duplicate_count,
                       GROUP_CONCAT(mf.path, '||') paths,
                       GROUP_CONCAT(COALESCE(s.name,''), '||') show_names,
                       GROUP_CONCAT(COALESCE(e.season,''), '||') seasons,
                       GROUP_CONCAT(COALESCE(e.episode,''), '||') episodes
                FROM media_fingerprints mf
                LEFT JOIN episodes e ON e.id = mf.episode_id
                LEFT JOIN shows s ON s.id = e.show_id
                GROUP BY mf.fingerprint, mf.file_size
                HAVING COUNT(*) > 1
                ORDER BY duplicate_count DESC, mf.file_size DESC
                LIMIT ?
            """
        else:
            sql = """
                SELECT mf.fingerprint, mf.file_size, COUNT(*) duplicate_count,
                       GROUP_CONCAT(mf.path, '||') paths,
                       '' show_names, '' seasons, '' episodes
                FROM media_fingerprints mf
                GROUP BY mf.fingerprint, mf.file_size
                HAVING COUNT(*) > 1
                ORDER BY duplicate_count DESC, mf.file_size DESC
                LIMIT ?
            """
        rows = conn.execute(sql, (limit,)).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        paths = [p for p in (row["paths"] or "").split("||") if p]
        results.append(
            {
                "fingerprint": row["fingerprint"],
                "file_size": row["file_size"],
                "duplicate_count": row["duplicate_count"],
                "paths": paths,
                "show_names": [p for p in (row["show_names"] or "").split("||") if p],
                "seasons": [p for p in (row["seasons"] or "").split("||") if p != ""],
                "episodes": [p for p in (row["episodes"] or "").split("||") if p != ""],
                "safe_action": "review",
            }
        )
    return results


def ensure_maintenance_tables(db_path: str | Path) -> None:
    """Create operator/audit tables used by library health and cleanup workflows."""
    with dbcore.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS duplicate_cleanup_actions(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              fingerprint TEXT,
              source_path TEXT NOT NULL,
              trash_path TEXT,
              action TEXT NOT NULL,
              status TEXT NOT NULL,
              message TEXT,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP,
              restored_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_duplicate_cleanup_fingerprint
              ON duplicate_cleanup_actions(fingerprint, created_at);
            """
        )


def _episode_file_samples(conn, sample_limit: int) -> tuple[int, list[dict[str, Any]], int, list[dict[str, Any]]]:
    """Return missing-on-disk and no-location episode counts/samples."""
    if not _has_columns(conn, "episodes", "id", "show_id", "season", "episode", "location"):
        return 0, [], 0, []
    has_status = _has_columns(conn, "episodes", "status")
    has_name = _has_columns(conn, "episodes", "name")
    has_show_name = _has_columns(conn, "shows", "id", "name")
    status_expr = "e.status" if has_status else "'' AS status"
    name_expr = "e.name" if has_name else "'' AS name"
    show_expr = "COALESCE(s.name,'Unknown') show_name" if has_show_name else "'Unknown' show_name"
    join_expr = "LEFT JOIN shows s ON s.id=e.show_id" if has_show_name else ""

    no_location_count = _count(conn, "SELECT COUNT(*) FROM episodes WHERE COALESCE(TRIM(location),'')=''")
    no_location_rows = _dict_rows(
        conn,
        f"""
        SELECT e.id, {show_expr}, e.season, e.episode, {name_expr}, {status_expr}, e.location
        FROM episodes e {join_expr}
        WHERE COALESCE(TRIM(e.location),'')=''
        ORDER BY show_name COLLATE NOCASE, e.season, e.episode
        LIMIT ?
        """,
        (sample_limit,),
    )

    rows_with_paths = _dict_rows(
        conn,
        f"""
        SELECT e.id, {show_expr}, e.season, e.episode, {name_expr}, {status_expr}, e.location
        FROM episodes e {join_expr}
        WHERE COALESCE(TRIM(e.location),'')<>''
        ORDER BY show_name COLLATE NOCASE, e.season, e.episode
        """,
    )
    missing_rows: list[dict[str, Any]] = []
    missing_count = 0
    for row in rows_with_paths:
        path_text = str(row.get("location") or "")
        if path_text and not Path(path_text).exists():
            missing_count += 1
            if len(missing_rows) < sample_limit:
                row["problem"] = "file_not_found"
                missing_rows.append(row)
    return missing_count, missing_rows, no_location_count, no_location_rows


def library_health_report(db_path: str | Path, *, duplicate_limit: int = 25, sample_limit: int = 25) -> dict[str, Any]:
    """Return an operator-focused health report for imports and library maintenance.

    This is intentionally defensive. The UI should render a useful report instead
    of a 500 error when a database is empty, partially upgraded, or imported from
    a legacy SickChill layout.
    """
    report: dict[str, Any] = {
        "ok": True,
        "schema_warnings": [],
        "counts": {
            "shows": 0,
            "episodes": 0,
            "downloaded_episodes": 0,
            "missing_episode_files": 0,
            "episodes_without_file_location": 0,
            "shows_missing_external_ids": 0,
            "shows_without_location": 0,
            "duplicate_groups": 0,
            "metadata_stale_or_missing": 0,
        },
        "samples": {
            "missing_episode_files": [],
            "episodes_without_file_location": [],
            "shows_missing_external_ids": [],
            "shows_without_location": [],
            "metadata_stale_or_missing": [],
            "duplicates": [],
        },
        "recommendations": [],
    }
    with dbcore.connect(db_path, wal=False, readonly=True) as conn:
        tables = _tables(conn)
        if "shows" not in tables:
            report["schema_warnings"].append("The shows table is not present yet. Run setup or import data first.")
        if "episodes" not in tables:
            report["schema_warnings"].append("The episodes table is not present yet. Run setup or import data first.")
        if "media_fingerprints" not in tables:
            report["schema_warnings"].append("The media fingerprint cache has not been built yet, so duplicate detection may be empty.")

        if "shows" in tables:
            show_cols = _columns(conn, "shows")
            report["counts"]["shows"] = _count(conn, "SELECT COUNT(*) FROM shows")
            if {"imdb_id", "tmdb_id", "tvdb_id"}.issubset(show_cols):
                report["counts"]["shows_missing_external_ids"] = _count(
                    conn,
                    "SELECT COUNT(*) FROM shows WHERE COALESCE(imdb_id,'')='' AND tmdb_id IS NULL AND tvdb_id IS NULL",
                )
                report["samples"]["shows_missing_external_ids"] = _dict_rows(
                    conn,
                    "SELECT id,name,imdb_id,tmdb_id,tvdb_id FROM shows WHERE COALESCE(imdb_id,'')='' AND tmdb_id IS NULL AND tvdb_id IS NULL ORDER BY name COLLATE NOCASE LIMIT ?",
                    (sample_limit,),
                )
            else:
                report["schema_warnings"].append("Some external-ID columns are missing; ID gap checks were skipped.")
            if "location" in show_cols:
                report["counts"]["shows_without_location"] = _count(conn, "SELECT COUNT(*) FROM shows WHERE COALESCE(TRIM(location),'')=''")
                report["samples"]["shows_without_location"] = _dict_rows(
                    conn,
                    "SELECT id,name,location FROM shows WHERE COALESCE(TRIM(location),'')='' ORDER BY name COLLATE NOCASE LIMIT ?",
                    (sample_limit,),
                )

        if "episodes" in tables:
            ep_cols = _columns(conn, "episodes")
            report["counts"]["episodes"] = _count(conn, "SELECT COUNT(*) FROM episodes")
            if "location" in ep_cols:
                report["counts"]["downloaded_episodes"] = _count(conn, "SELECT COUNT(*) FROM episodes WHERE COALESCE(TRIM(location),'')<>''")
                missing_count, missing_rows, no_location_count, no_location_rows = _episode_file_samples(conn, sample_limit)
                report["counts"]["missing_episode_files"] = missing_count
                report["samples"]["missing_episode_files"] = missing_rows
                report["counts"]["episodes_without_file_location"] = no_location_count
                report["samples"]["episodes_without_file_location"] = no_location_rows
            else:
                report["schema_warnings"].append("Episode location column is missing; file checks were skipped.")

        if "metadata_refresh_state" in tables and "shows" in tables and _has_columns(conn, "metadata_refresh_state", "show_id"):
            has_status = _has_columns(conn, "metadata_refresh_state", "last_status")
            has_refresh = _has_columns(conn, "metadata_refresh_state", "last_refresh")
            has_error = _has_columns(conn, "metadata_refresh_state", "last_error")
            status_check = "COALESCE(m.last_status,'') NOT IN ('ok','success')" if has_status else "1=1"
            report["counts"]["metadata_stale_or_missing"] = _count(
                conn,
                f"""
                SELECT COUNT(*) FROM shows s
                LEFT JOIN metadata_refresh_state m ON m.show_id=s.id
                WHERE m.show_id IS NULL OR {status_check}
                """,
            )
            select_status = "m.last_status" if has_status else "'' AS last_status"
            select_refresh = "m.last_refresh" if has_refresh else "'' AS last_refresh"
            select_error = "m.last_error" if has_error else "'' AS last_error"
            report["samples"]["metadata_stale_or_missing"] = _dict_rows(
                conn,
                f"""
                SELECT s.id,s.name,{select_refresh},{select_status},{select_error}
                FROM shows s LEFT JOIN metadata_refresh_state m ON m.show_id=s.id
                WHERE m.show_id IS NULL OR {status_check}
                ORDER BY s.name COLLATE NOCASE LIMIT ?
                """,
                (sample_limit,),
            )
        elif "shows" in tables:
            report["schema_warnings"].append("Metadata refresh state is not initialized yet; metadata stale checks may be incomplete.")

    duplicates = duplicate_candidates(db_path, limit=duplicate_limit)
    report["samples"]["duplicates"] = duplicates
    report["counts"]["duplicate_groups"] = len(duplicates)

    if report["counts"]["missing_episode_files"]:
        report["recommendations"].append("Some episode paths point to files that no longer exist. Review these before post-processing or cleanup.")
    if report["counts"]["episodes_without_file_location"]:
        report["recommendations"].append("Some episodes do not have a file location yet. This may be normal for wanted or unaired episodes.")
    if report["counts"]["shows_missing_external_ids"]:
        report["recommendations"].append("Refresh metadata for shows without IMDb/TMDb/TVDb identifiers.")
    if duplicates:
        report["recommendations"].append("Use duplicate cleanup preview before moving any file to managed trash.")
    if report["schema_warnings"]:
        report["recommendations"].append("Run database setup/migrations if this is an older or newly imported database.")
    if not report["recommendations"]:
        report["recommendations"].append("Library health looks good. Keep scheduled metadata refresh enabled.")
    return report


def duplicate_cleanup_preview(db_path: str | Path, *, keep_path: str | None = None, paths: list[str] | None = None, limit: int = 100) -> dict[str, Any]:
    """Build a no-write duplicate cleanup plan from fingerprint groups."""
    requested = set(paths or [])
    groups = duplicate_candidates(db_path, limit=limit)
    actions: list[dict[str, Any]] = []
    for group in groups:
        group_paths = list(group.get("paths") or [])
        if requested and not any(p in requested for p in group_paths):
            continue
        keep = keep_path if keep_path in group_paths else (group_paths[0] if group_paths else None)
        for path in group_paths:
            if path == keep:
                continue
            if requested and path not in requested:
                continue
            actions.append({
                "fingerprint": group.get("fingerprint"),
                "source_path": path,
                "keep_path": keep,
                "file_size": group.get("file_size"),
                "status": "planned",
                "action": "move_to_managed_trash",
            })
    return {"dry_run": True, "action_count": len(actions), "actions": actions}


def apply_duplicate_cleanup(db_path: str | Path, *, trash_root: str | Path, actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Move explicitly previewed duplicate files into managed trash and audit every result."""
    import shutil
    from datetime import datetime

    ensure_maintenance_tables(db_path)
    trash_root = Path(trash_root)
    batch_dir = trash_root / datetime.now().strftime("duplicate-cleanup-%Y%m%d-%H%M%S")
    batch_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    with dbcore.connect(db_path) as conn:
        for item in actions:
            src = Path(str(item.get("source_path") or ""))
            fingerprint = item.get("fingerprint")
            if not src.exists() or not src.is_file():
                status = "skipped"
                message = "Source file does not exist or is not a regular file."
                trash_path = None
            else:
                target = batch_dir / src.name
                n = 1
                while target.exists():
                    target = batch_dir / f"{src.stem}.{n}{src.suffix}"
                    n += 1
                shutil.move(str(src), str(target))
                status = "moved"
                message = "Moved to managed trash."
                trash_path = str(target)
            conn.execute(
                """
                INSERT INTO duplicate_cleanup_actions(fingerprint,source_path,trash_path,action,status,message)
                VALUES(?,?,?,?,?,?)
                """,
                (fingerprint, str(src), trash_path, "move_to_managed_trash", status, message),
            )
            results.append({"source_path": str(src), "trash_path": trash_path, "status": status, "message": message})
        conn.commit()
    return {"ok": True, "trash_batch": str(batch_dir), "results": results, "moved": sum(1 for r in results if r["status"] == "moved")}
