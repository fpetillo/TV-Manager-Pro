from __future__ import annotations
import sqlite3
from pathlib import Path

DEFAULT_BUSY_TIMEOUT_MS = 30000

class ManagedConnection(sqlite3.Connection):
    """SQLite connection that commits/rolls back and closes at context exit."""
    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False

def _raw_connect(target, *, uri=False, timeout=30):
    return sqlite3.connect(target, uri=uri, timeout=timeout, factory=ManagedConnection)

def connect(path, *, wal=True, readonly=False):
    path = Path(path)
    if readonly:
        c = _raw_connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    else:
        c = _raw_connect(path)
    c.row_factory = sqlite3.Row
    c.execute(f"PRAGMA busy_timeout={DEFAULT_BUSY_TIMEOUT_MS}")
    c.execute("PRAGMA foreign_keys=ON")
    if wal and not readonly:
        try:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.DatabaseError:
            pass
    return c

def quick_check(path):
    with connect(path, wal=False, readonly=True) as c:
        return c.execute("PRAGMA quick_check").fetchone()[0]

def online_backup(source, destination):
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with connect(source, wal=False, readonly=True) as src:
        with _raw_connect(destination) as dst:
            src.backup(dst)
    return destination
