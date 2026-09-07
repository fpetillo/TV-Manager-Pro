from __future__ import annotations
from datetime import datetime
from pathlib import Path
import json
import dbcore

VERSION=1717
VERSION_NAME="17.1.7"

def _has_column(c,table,column):
    return column in {r["name"] for r in c.execute(f'PRAGMA table_info("{table}")').fetchall()}

def _has_table(c, table):
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None

def migrate(db_path):
    db_path=Path(db_path)
    backup=None
    if db_path.exists() and db_path.stat().st_size:
        backups=db_path.parent/"backups";backups.mkdir(exist_ok=True)
        marker=backups/"v16-migration-backup.done"
        if not marker.exists():
            stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
            backup=backups/f"tvmanager-before-v16-{stamp}.db"
            dbcore.online_backup(db_path,backup)
            marker.write_text(backup.name,encoding="utf-8")
    with dbcore.connect(db_path) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS schema_migrations(
          version INTEGER PRIMARY KEY,version_name TEXT NOT NULL,
          applied_at TEXT DEFAULT CURRENT_TIMESTAMP,details_json TEXT);
        CREATE TABLE IF NOT EXISTS acquisition_episode_links(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          acquisition_type TEXT NOT NULL,acquisition_id INTEGER NOT NULL,
          episode_id INTEGER NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(acquisition_type,acquisition_id,episode_id));
        CREATE INDEX IF NOT EXISTS idx_acq_episode ON acquisition_episode_links(episode_id,acquisition_type);
        CREATE TABLE IF NOT EXISTS scheduler_runs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,job_name TEXT NOT NULL,
          started_at TEXT DEFAULT CURRENT_TIMESTAMP,finished_at TEXT,
          status TEXT DEFAULT 'Running',message TEXT);
        """)
        if not _has_column(c,"season_pack_downloads","progress"):
            c.execute("ALTER TABLE season_pack_downloads ADD COLUMN progress REAL DEFAULT 0")
        if not _has_column(c,"season_pack_downloads","error"):
            c.execute("ALTER TABLE season_pack_downloads ADD COLUMN error TEXT")
        if not _has_column(c,"season_pack_downloads","updated_at"):
            c.execute("ALTER TABLE season_pack_downloads ADD COLUMN updated_at TEXT")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS subtitle_jobs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          episode_id INTEGER NOT NULL,
          language TEXT DEFAULT 'en',
          status TEXT DEFAULT 'Pending',
          attempts INTEGER DEFAULT 0,
          last_error TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(episode_id,language)
        );
        """)
        c.executescript("""
        CREATE TABLE IF NOT EXISTS acquisition_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          acquisition_type TEXT NOT NULL, acquisition_id INTEGER NOT NULL,
          from_state TEXT, to_state TEXT NOT NULL, message TEXT, details_json TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS upgrade_replacements(
          id INTEGER PRIMARY KEY AUTOINCREMENT, episode_id INTEGER NOT NULL,
          old_path TEXT,replacement_path TEXT,trash_path TEXT,old_release TEXT,new_release TEXT,
          old_quality TEXT,new_quality TEXT,status TEXT DEFAULT 'Pending',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,completed_at TEXT,restored_at TEXT
        );
        """)
        if not _has_column(c,"subtitle_jobs","next_attempt_at"):
            c.execute("ALTER TABLE subtitle_jobs ADD COLUMN next_attempt_at TEXT")
        if not _has_column(c,"subtitle_jobs","priority"):
            c.execute("ALTER TABLE subtitle_jobs ADD COLUMN priority INTEGER DEFAULT 0")
        if not _has_column(c,"subtitle_jobs","provider"):
            c.execute("ALTER TABLE subtitle_jobs ADD COLUMN provider TEXT")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS media_fingerprints(
          path TEXT PRIMARY KEY,file_size INTEGER NOT NULL,mtime_ns INTEGER,
          fingerprint TEXT NOT NULL,episode_id INTEGER,checked_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_media_fingerprint ON media_fingerprints(fingerprint,file_size);
        CREATE TABLE IF NOT EXISTS scheduler_leases(
          job_name TEXT PRIMARY KEY,owner TEXT NOT NULL,acquired_at TEXT NOT NULL,expires_at TEXT NOT NULL
        );
        """)
        c.executescript("""
        CREATE TABLE IF NOT EXISTS admin_users(
          id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL,salt TEXT NOT NULL,iterations INTEGER NOT NULL,
          enabled INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,last_login TEXT
        );
        CREATE TABLE IF NOT EXISTS login_attempts(
          id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT,remote_addr TEXT,
          success INTEGER DEFAULT 0,attempted_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_login_attempts_addr ON login_attempts(remote_addr,attempted_at);
        CREATE TABLE IF NOT EXISTS security_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,event_type TEXT NOT NULL,username TEXT,
          remote_addr TEXT,detail TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS naming_presets(
          id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,pattern TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS metadata_refresh_state(
          show_id INTEGER PRIMARY KEY,last_refresh TEXT,last_status TEXT,last_error TEXT,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        c.execute("""INSERT OR IGNORE INTO schema_migrations(version,version_name,details_json)
                     VALUES(?,?,?)""",(16,"16.0",json.dumps({
                         "features":["browser authentication","CSRF protection","LAN binding guard",
                                     "naming settings UI","automatic postprocessing scheduler"]
                     })))
        c.executescript("""
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
        """)

        # v17.1.7 startup hardening: early user databases may lack core episode/show
        # columns that app.py and engine.py expect before later feature-specific migrations run.
        if _has_table(c, "shows"):
            for name, definition in {
                "imdb_id": "TEXT",
            "tvdb_id": "INTEGER",
            "legacy_indexer_id": "INTEGER",
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
            }.items():
                if not _has_column(c, "shows", name):
                    c.execute(f'ALTER TABLE shows ADD COLUMN "{name}" {definition}')
        if _has_table(c, "episodes"):
            for name, definition in {
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
            }.items():
                if not _has_column(c, "episodes", name):
                    c.execute(f'ALTER TABLE episodes ADD COLUMN "{name}" {definition}')

        c.executescript("""
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
        """)
        c.execute("""INSERT OR IGNORE INTO schema_migrations(version,version_name,details_json)
                     VALUES(?,?,?)""",(17,"17.0",json.dumps({
                         "features":["SickChill dry-run import analysis","legacy identity map",
                                     "per-item import audit trail","duplicate candidate API"]
                     })))
        c.execute("""INSERT OR IGNORE INTO schema_migrations(version,version_name,details_json)
                     VALUES(?,?,?)""",(VERSION,VERSION_NAME,json.dumps({
                         "features":["Import Center UI","library health dashboard",
                                     "safe duplicate cleanup preview/apply workflow"]
                     })))
        c.commit()
    result=dbcore.quick_check(db_path)
    if result!="ok":
        raise RuntimeError(f"Database integrity check failed after migration: {result}")
    return {"version":VERSION_NAME,"backup":str(backup) if backup else None,"quick_check":result}
