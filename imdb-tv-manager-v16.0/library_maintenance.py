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
