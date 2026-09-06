from __future__ import annotations

from pathlib import Path
from typing import Any

import dbcore


def duplicate_candidates(db_path: str | Path, *, limit: int = 100) -> list[dict[str, Any]]:
    """Return likely duplicate media files from the v15+ fingerprint cache."""
    with dbcore.connect(db_path, wal=False, readonly=True) as conn:
        tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "media_fingerprints" not in tables:
            return []
        rows = conn.execute(
            """
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
            """,
            (limit,),
        ).fetchall()
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


def library_health_report(db_path: str | Path, *, duplicate_limit: int = 25, sample_limit: int = 25) -> dict[str, Any]:
    """Return an operator-focused health report for imports and library maintenance."""
    with dbcore.connect(db_path, wal=False, readonly=True) as conn:
        tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        def count(sql: str, params: tuple = ()) -> int:
            return int(conn.execute(sql, params).fetchone()[0])
        report: dict[str, Any] = {
            "counts": {
                "shows": count("SELECT COUNT(*) FROM shows") if "shows" in tables else 0,
                "episodes": count("SELECT COUNT(*) FROM episodes") if "episodes" in tables else 0,
                "downloaded_episodes": count("SELECT COUNT(*) FROM episodes WHERE COALESCE(TRIM(location),'')<>''") if "episodes" in tables else 0,
                "missing_episode_files": 0,
                "shows_missing_external_ids": 0,
                "shows_without_location": 0,
                "duplicate_groups": 0,
                "metadata_stale_or_missing": 0,
            },
            "samples": {
                "missing_episode_files": [],
                "shows_missing_external_ids": [],
                "shows_without_location": [],
                "metadata_stale_or_missing": [],
                "duplicates": [],
            },
            "recommendations": [],
        }
        if "episodes" in tables:
            rows = conn.execute(
                """
                SELECT e.id, COALESCE(s.name,'Unknown') show_name, e.season, e.episode, e.name, e.status, e.location
                FROM episodes e LEFT JOIN shows s ON s.id=e.show_id
                WHERE COALESCE(TRIM(e.location),'')=''
                ORDER BY s.name COLLATE NOCASE, e.season, e.episode
                LIMIT ?
                """,
                (sample_limit,),
            ).fetchall()
            report["counts"]["missing_episode_files"] = count("SELECT COUNT(*) FROM episodes WHERE COALESCE(TRIM(location),'')=''")
            report["samples"]["missing_episode_files"] = [dict(r) for r in rows]
        if "shows" in tables:
            report["counts"]["shows_missing_external_ids"] = count(
                "SELECT COUNT(*) FROM shows WHERE COALESCE(imdb_id,'')='' AND tmdb_id IS NULL AND tvdb_id IS NULL"
            )
            report["counts"]["shows_without_location"] = count("SELECT COUNT(*) FROM shows WHERE COALESCE(TRIM(location),'')=''")
            report["samples"]["shows_missing_external_ids"] = [dict(r) for r in conn.execute(
                "SELECT id,name,imdb_id,tmdb_id,tvdb_id FROM shows WHERE COALESCE(imdb_id,'')='' AND tmdb_id IS NULL AND tvdb_id IS NULL ORDER BY name COLLATE NOCASE LIMIT ?",
                (sample_limit,),
            ).fetchall()]
            report["samples"]["shows_without_location"] = [dict(r) for r in conn.execute(
                "SELECT id,name,location FROM shows WHERE COALESCE(TRIM(location),'')='' ORDER BY name COLLATE NOCASE LIMIT ?",
                (sample_limit,),
            ).fetchall()]
        if "metadata_refresh_state" in tables and "shows" in tables:
            report["counts"]["metadata_stale_or_missing"] = count(
                """
                SELECT COUNT(*) FROM shows s
                LEFT JOIN metadata_refresh_state m ON m.show_id=s.id
                WHERE m.show_id IS NULL OR COALESCE(m.last_status,'') NOT IN ('ok','success')
                """
            )
            report["samples"]["metadata_stale_or_missing"] = [dict(r) for r in conn.execute(
                """
                SELECT s.id,s.name,m.last_refresh,m.last_status,m.last_error
                FROM shows s LEFT JOIN metadata_refresh_state m ON m.show_id=s.id
                WHERE m.show_id IS NULL OR COALESCE(m.last_status,'') NOT IN ('ok','success')
                ORDER BY s.name COLLATE NOCASE LIMIT ?
                """,
                (sample_limit,),
            ).fetchall()]
    duplicates = duplicate_candidates(db_path, limit=duplicate_limit)
    report["samples"]["duplicates"] = duplicates
    report["counts"]["duplicate_groups"] = len(duplicates)
    if report["counts"]["missing_episode_files"]:
        report["recommendations"].append("Review missing episode files before enabling automated post-processing.")
    if report["counts"]["shows_missing_external_ids"]:
        report["recommendations"].append("Refresh metadata for shows without IMDb/TMDb/TVDb identifiers.")
    if duplicates:
        report["recommendations"].append("Use duplicate cleanup preview before moving any file to managed trash.")
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
