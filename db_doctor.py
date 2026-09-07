from __future__ import annotations

import json
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / "tvmanager.db"
LOG = BASE / "diagnostics" / "startup-db-repair.json"

SHOW_COLUMNS = {
    "tmdb_id": "INTEGER",
    "imdb_id": "TEXT",
    "tvdb_id": "INTEGER",
    "legacy_indexer_id": "INTEGER",
    "name": "TEXT",
    "original_name": "TEXT",
    "first_air_date": "TEXT",
    "overview": "TEXT",
    "poster": "TEXT",
    "vote_average": "REAL",
    "location": "TEXT",
    "network": "TEXT",
    "genre": "TEXT",
    "quality": "TEXT",
    "paused": "INTEGER DEFAULT 0",
    "anime": "INTEGER DEFAULT 0",
    "status": "TEXT DEFAULT 'Wanted'",
    "legacy_data": "TEXT",
    "added_at": "TEXT",
    "monitor_new": "INTEGER DEFAULT 1",
    "search_enabled": "INTEGER DEFAULT 1",
    "preferred_words": "TEXT",
    "required_words": "TEXT",
    "ignored_words": "TEXT",
    "season_folders": "INTEGER DEFAULT 1",
    "scene_numbering": "INTEGER DEFAULT 0",
    "air_by_date": "INTEGER DEFAULT 0",
    "sports": "INTEGER DEFAULT 0",
    "metadata_enabled": "INTEGER DEFAULT 1",
    "quality_profile_id": "INTEGER",
    "favorite": "INTEGER DEFAULT 0",
    "retention_policy_id": "INTEGER",
    "trakt_id": "INTEGER",
    "trakt_slug": "TEXT",
}

EPISODE_COLUMNS = {
    "show_id": "INTEGER",
    "season": "INTEGER DEFAULT 0",
    "episode": "INTEGER DEFAULT 0",
    "name": "TEXT",
    "airdate": "TEXT",
    "status": "TEXT DEFAULT 'Wanted'",
    "location": "TEXT",
    "file_size": "INTEGER",
    "release_name": "TEXT",
    "quality": "TEXT",
    "legacy_data": "TEXT",
    "monitored": "INTEGER DEFAULT 1",
    "last_search": "TEXT",
    "search_count": "INTEGER DEFAULT 0",
    "overview": "TEXT",
    "still_url": "TEXT",
    "still_path": "TEXT",
    "tmdb_episode_id": "INTEGER",
    "metadata_updated_at": "TEXT",
    "ignored": "INTEGER DEFAULT 0",
    "ignored_reason": "TEXT",
    "ignored_at": "TEXT",
    "ignored_source": "TEXT",
    "managed_note": "TEXT",
}

CREATE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS shows(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tmdb_id INTEGER UNIQUE,
      imdb_id TEXT,
      tvdb_id INTEGER,
      legacy_indexer_id INTEGER,
      name TEXT NOT NULL,
      original_name TEXT,
      first_air_date TEXT,
      overview TEXT,
      poster TEXT,
      vote_average REAL,
      location TEXT,
      network TEXT,
      genre TEXT,
      quality TEXT,
      paused INTEGER DEFAULT 0,
      anime INTEGER DEFAULT 0,
      status TEXT DEFAULT 'Wanted',
      legacy_data TEXT,
      added_at TEXT DEFAULT CURRENT_TIMESTAMP,
      monitor_new INTEGER DEFAULT 1,
      search_enabled INTEGER DEFAULT 1,
      preferred_words TEXT,
      required_words TEXT,
      ignored_words TEXT,
      season_folders INTEGER DEFAULT 1,
      scene_numbering INTEGER DEFAULT 0,
      air_by_date INTEGER DEFAULT 0,
      sports INTEGER DEFAULT 0,
      metadata_enabled INTEGER DEFAULT 1,
      quality_profile_id INTEGER,
      favorite INTEGER DEFAULT 0,
      retention_policy_id INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS episodes(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      show_id INTEGER NOT NULL,
      season INTEGER NOT NULL DEFAULT 0,
      episode INTEGER NOT NULL DEFAULT 0,
      name TEXT,
      airdate TEXT,
      status TEXT DEFAULT 'Wanted',
      location TEXT,
      file_size INTEGER,
      release_name TEXT,
      quality TEXT,
      legacy_data TEXT,
      monitored INTEGER DEFAULT 1,
      last_search TEXT,
      search_count INTEGER DEFAULT 0,
      overview TEXT,
      still_url TEXT,
      still_path TEXT,
      tmdb_episode_id INTEGER,
      metadata_updated_at TEXT,
      ignored INTEGER DEFAULT 0,
      ignored_reason TEXT,
      ignored_at TEXT,
      ignored_source TEXT,
      managed_note TEXT,
      UNIQUE(show_id,season,episode)
    )
    """,
    "CREATE TABLE IF NOT EXISTS settings(section TEXT NOT NULL,name TEXT NOT NULL,value TEXT,is_secret INTEGER NOT NULL DEFAULT 0,source TEXT NOT NULL DEFAULT 'app',updated_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(section,name))",
    "CREATE TABLE IF NOT EXISTS import_runs(id INTEGER PRIMARY KEY AUTOINCREMENT,source_name TEXT,shows_found INTEGER DEFAULT 0,shows_imported INTEGER DEFAULT 0,shows_skipped INTEGER DEFAULT 0,episodes_found INTEGER DEFAULT 0,episodes_imported INTEGER DEFAULT 0,episodes_skipped INTEGER DEFAULT 0,imported_at TEXT DEFAULT CURRENT_TIMESTAMP)",
    "CREATE TABLE IF NOT EXISTS legacy_identity_map(source_name TEXT NOT NULL,legacy_show_id INTEGER,tvmanager_show_id INTEGER NOT NULL,tvdb_id INTEGER,imdb_id TEXT,show_name TEXT,imported_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(source_name, legacy_show_id))",
    "CREATE TABLE IF NOT EXISTS import_run_details(id INTEGER PRIMARY KEY AUTOINCREMENT,import_run_id INTEGER,source_name TEXT NOT NULL,item_type TEXT NOT NULL,source_id TEXT,tvmanager_id INTEGER,action TEXT NOT NULL,message TEXT,details_json TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
    "CREATE TABLE IF NOT EXISTS duplicate_cleanup_actions(id INTEGER PRIMARY KEY AUTOINCREMENT,fingerprint TEXT,source_path TEXT NOT NULL,trash_path TEXT,action TEXT NOT NULL,status TEXT NOT NULL,message TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,restored_at TEXT)",
    "CREATE TABLE IF NOT EXISTS metadata_refresh_state(show_id INTEGER PRIMARY KEY,last_refresh TEXT,last_status TEXT,last_error TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)",
    "CREATE TABLE IF NOT EXISTS media_fingerprints(path TEXT PRIMARY KEY,file_size INTEGER NOT NULL,mtime_ns INTEGER,fingerprint TEXT NOT NULL,episode_id INTEGER,checked_at TEXT DEFAULT CURRENT_TIMESTAMP)",
    "CREATE TABLE IF NOT EXISTS scene_exceptions(id INTEGER PRIMARY KEY AUTOINCREMENT,show_id INTEGER NOT NULL,exception_name TEXT NOT NULL,source TEXT DEFAULT 'manual',notes TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(show_id, exception_name))",
    "CREATE TABLE IF NOT EXISTS mass_update_history(id INTEGER PRIMARY KEY AUTOINCREMENT,action TEXT NOT NULL,filter_json TEXT,affected INTEGER DEFAULT 0,message TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_shows_imdb ON shows(imdb_id)",
    "CREATE INDEX IF NOT EXISTS idx_shows_tvdb ON shows(tvdb_id)",
    "CREATE INDEX IF NOT EXISTS idx_shows_legacy ON shows(legacy_indexer_id)",
    "CREATE INDEX IF NOT EXISTS idx_shows_name_status ON shows(name COLLATE NOCASE, status)",
    "CREATE INDEX IF NOT EXISTS idx_shows_status ON shows(status)",
    "CREATE INDEX IF NOT EXISTS idx_shows_network ON shows(network COLLATE NOCASE)",
    "CREATE INDEX IF NOT EXISTS idx_shows_trakt ON shows(trakt_id)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_show_airdate ON episodes(show_id, airdate)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_show_season_episode_fast ON episodes(show_id, season, episode, id)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_show_status_fast ON episodes(show_id, status, season, episode)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_show_ignored_fast ON episodes(show_id, ignored, status, season, episode)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_show_name_fast ON episodes(show_id, name COLLATE NOCASE)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_artwork ON episodes(show_id, still_url, still_path)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_show_location ON episodes(show_id, location)",
    "CREATE INDEX IF NOT EXISTS idx_media_fingerprint ON media_fingerprints(fingerprint,file_size)",
    "CREATE INDEX IF NOT EXISTS idx_duplicate_cleanup_fingerprint ON duplicate_cleanup_actions(fingerprint, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_scene_exceptions_show ON scene_exceptions(show_id)",
]


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def _ensure_columns(conn: sqlite3.Connection, table: str, required: dict[str, str]) -> list[str]:
    existing = _columns(conn, table)
    added: list[str] = []
    for name, definition in required.items():
        if name not in existing:
            conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')
            added.append(f"{table}.{name}")
    return added



def _write_report(report: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(report, indent=2), encoding="utf-8")


def quick_check_database(db_path: str | Path = DB) -> dict:
    """Return a small integrity report without mutating the database."""
    db_path = Path(db_path)
    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "database": str(db_path),
        "exists": db_path.exists(),
        "size": db_path.stat().st_size if db_path.exists() else 0,
        "quick_check": None,
        "ok": True,
        "error": None,
    }
    if not db_path.exists() or report["size"] == 0:
        return report
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        value = conn.execute("PRAGMA quick_check").fetchone()
        report["quick_check"] = value[0] if value else "no result"
        report["ok"] = str(report["quick_check"]).lower() == "ok"
    except sqlite3.DatabaseError as exc:
        report["ok"] = False
        report["quick_check"] = "database_error"
        report["error"] = str(exc)
    finally:
        if conn is not None:
            conn.close()
    return report


class DatabaseSafetyError(RuntimeError):
    pass


def repair(db_path: str | Path = DB) -> dict:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    (db_path.parent / "diagnostics").mkdir(exist_ok=True)
    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "database": str(db_path),
        "created_or_verified_tables": [],
        "added_columns": [],
        "indexes": [],
        "quick_check": None,
        "ok": True,
        "error": None,
    }

    preflight = quick_check_database(db_path)
    if not preflight.get("ok", False):
        report["ok"] = False
        report["quick_check"] = preflight.get("quick_check")
        report["error"] = preflight.get("error") or "SQLite PRAGMA quick_check did not return ok"
        _write_report(report)
        raise DatabaseSafetyError(
            "tvmanager.db failed integrity check before schema repair. "
            "Do not continue writing to this database. Restore a known-good backup. "
            f"quick_check={report['quick_check']} error={report['error']}"
        )

    conn = sqlite3.connect(db_path)
    try:
        for sql in CREATE_TABLES:
            conn.execute(sql)
        report["created_or_verified_tables"] = ["shows", "episodes", "settings", "import_runs", "legacy_identity_map", "import_run_details", "duplicate_cleanup_actions", "metadata_refresh_state", "media_fingerprints"]
        report["added_columns"].extend(_ensure_columns(conn, "shows", SHOW_COLUMNS))
        report["added_columns"].extend(_ensure_columns(conn, "episodes", EPISODE_COLUMNS))
        # Backfill statuses so downstream SQL gets useful values, not NULL-only rows.
        if "status" in _columns(conn, "episodes"):
            conn.execute("UPDATE episodes SET status='Wanted' WHERE status IS NULL OR TRIM(status)='' ")
        if "status" in _columns(conn, "shows"):
            conn.execute("UPDATE shows SET status='Wanted' WHERE status IS NULL OR TRIM(status)='' ")
        for sql in INDEXES:
            conn.execute(sql)
            report["indexes"].append(sql.split("IF NOT EXISTS ", 1)[-1].split(" ON ", 1)[0])
        report["quick_check"] = conn.execute("PRAGMA quick_check").fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    _write_report(report)
    return report


if __name__ == "__main__":
    try:
        result = repair()
        print("TV Manager database startup repair complete")
        print(json.dumps(result, indent=2))
    except DatabaseSafetyError as exc:
        print("", file=sys.stderr)
        print("TV Manager database safety check failed.", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        print("", file=sys.stderr)
        print("Recommended recovery:", file=sys.stderr)
        print("  1. Stop all TV Manager/Python processes.", file=sys.stderr)
        print("  2. Make a safety copy of the current tvmanager.db.", file=sys.stderr)
        print("  3. Restore a known-good backup from backups\\ or a tvmanager-before-*.db file.", file=sys.stderr)
        print("  4. Restart TV Manager and check /api/build-info.", file=sys.stderr)
        print("", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"TV Manager database startup repair failed: {exc}", file=sys.stderr)
        sys.exit(1)
