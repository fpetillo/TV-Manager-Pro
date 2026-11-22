"""Database speed-ups (v18.23.0): extra indexes, planner statistics and log retention.

Everything here is safe to run repeatedly. Indexes are created with IF NOT EXISTS; retention
deletes only log rows older than the configured number of days (0 keeps everything).
"""
from __future__ import annotations

import logging
import sqlite3

log = logging.getLogger("tvmanager.performance")

# Each entry: (table, required columns, CREATE INDEX statement).
INDEXES = [
    ("activity_log", {"level", "created_at"},
     "CREATE INDEX IF NOT EXISTS idx_activity_level_nocase ON activity_log(level COLLATE NOCASE, created_at)"),
    ("activity_log", {"event_type", "created_at"},
     "CREATE INDEX IF NOT EXISTS idx_activity_event_nocase ON activity_log(event_type COLLATE NOCASE, created_at)"),
    ("activity_log", {"show_id"},
     "CREATE INDEX IF NOT EXISTS idx_activity_show ON activity_log(show_id)"),
    ("scheduler_runs", {"job_name", "id"},
     "CREATE INDEX IF NOT EXISTS idx_scheduler_runs_job ON scheduler_runs(job_name, id)"),
    ("api_access_log", {"created_at"},
     "CREATE INDEX IF NOT EXISTS idx_api_access_created ON api_access_log(created_at)"),
    ("postprocess_history", {"processed_at"},
     "CREATE INDEX IF NOT EXISTS idx_postprocess_history_date ON postprocess_history(processed_at)"),
    ("downloads", {"status"},
     "CREATE INDEX IF NOT EXISTS idx_downloads_status ON downloads(status COLLATE NOCASE, episode_id)"),
    ("episodes", {"status"},
     "CREATE INDEX IF NOT EXISTS idx_episodes_status_nocase ON episodes(status COLLATE NOCASE)"),
    ("episodes", {"airdate"},
     "CREATE INDEX IF NOT EXISTS idx_episodes_airdate ON episodes(airdate)"),
]

# setting name -> (table, timestamp column, default days)
RETENTION = {
    "activity_log_retention_days": ("activity_log", "created_at", 180),
    "api_access_log_retention_days": ("api_access_log", "created_at", 30),
    "scheduler_runs_retention_days": ("scheduler_runs", "started_at", 90),
}


def _columns(conn, table):
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}


def ensure_indexes(conn) -> list[str]:
    created = []
    existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    for table, needed, sql in INDEXES:
        name = sql.split("EXISTS", 1)[1].split()[0]
        if name in existing:
            continue
        if not needed.issubset(_columns(conn, table)):
            continue
        conn.execute(sql)
        created.append(name)
    if created:
        # Fresh statistics so SQLite's planner actually picks the new indexes.
        conn.execute("ANALYZE")
    return created


def optimize(conn) -> None:
    """Cheap planner refresh (SQLite only re-analyzes tables that changed a lot)."""
    try:
        conn.execute("PRAGMA optimize")
    except sqlite3.DatabaseError:
        pass


def prune_logs(conn, get_setting) -> dict[str, int]:
    """Delete log rows older than each table's retention setting. Returns rows removed per table."""
    removed = {}
    for setting, (table, column, default) in RETENTION.items():
        try:
            days = int(str(get_setting("TVManager", setting, default)).strip())
        except (TypeError, ValueError):
            days = default
        if days <= 0 or column not in _columns(conn, table):
            continue
        cur = conn.execute(f'DELETE FROM "{table}" WHERE "{column}" < datetime(\'now\', ?)', (f"-{days} days",))
        if cur.rowcount:
            removed[table] = cur.rowcount
    return removed
