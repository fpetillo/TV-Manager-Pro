from __future__ import annotations
import sqlite3
import threading
import time
from pathlib import Path

# v17.20: TV Manager can run scheduler jobs, web requests, metadata refreshes,
# post-processing, downloader polling and log writes at the same time. SQLite is
# reliable for this workload, but it is still a single-writer database. This
# module serializes in-process writers and gives other processes a longer busy
# timeout so background jobs do not crash with "database is locked" when two
# operators or jobs write at once.
DEFAULT_BUSY_TIMEOUT_MS = 120000
DEFAULT_READ_BUSY_TIMEOUT_MS = 5000
DEFAULT_TIMEOUT_SECONDS = DEFAULT_BUSY_TIMEOUT_MS / 1000
DEFAULT_READ_TIMEOUT_SECONDS = DEFAULT_READ_BUSY_TIMEOUT_MS / 1000
_WRITE_LOCK = threading.RLock()
_TRANSIENT_LOCK_ERRORS = ("database is locked", "database table is locked", "database is busy")


def is_lock_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(x in msg for x in _TRANSIENT_LOCK_ERRORS)


class ManagedConnection(sqlite3.Connection):
    """SQLite connection that commits/rolls back and closes at context exit.

    Writable connections hold TV Manager's process-wide SQLite writer lock until
    closed. That prevents two local background threads from opening competing
    write transactions. Read-only connections do not take the lock.
    """

    _tvmanager_write_locked = False
    _tvmanager_closed = False

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False

    def close(self):  # noqa: D401 - inherited behavior with lock release
        if getattr(self, "_tvmanager_closed", False):
            return
        try:
            super().close()
        finally:
            self._tvmanager_closed = True
            if getattr(self, "_tvmanager_write_locked", False):
                self._tvmanager_write_locked = False
                _WRITE_LOCK.release()


def _raw_connect(target, *, uri=False, timeout=DEFAULT_TIMEOUT_SECONDS):
    return sqlite3.connect(target, uri=uri, timeout=timeout, factory=ManagedConnection)


def connect(path, *, wal=True, readonly=False):
    path = Path(path)
    if readonly:
        # Read-only UI requests must not wait behind long maintenance writers for minutes.
        # If the database is busy, fail quickly so the page can show a retryable message
        # instead of looking hung.
        c = _raw_connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=DEFAULT_READ_TIMEOUT_SECONDS)
    else:
        _WRITE_LOCK.acquire()
        try:
            c = _raw_connect(path)
            c._tvmanager_write_locked = True
        except Exception:
            _WRITE_LOCK.release()
            raise
    c.row_factory = sqlite3.Row
    c.execute(f"PRAGMA busy_timeout={DEFAULT_READ_BUSY_TIMEOUT_MS if readonly else DEFAULT_BUSY_TIMEOUT_MS}")
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


def retry(operation, *, attempts=6, first_delay=0.25, max_delay=5.0):
    """Run a SQLite operation with retry for transient external lock errors."""
    delay = float(first_delay)
    last = None
    for attempt in range(1, max(1, int(attempts)) + 1):
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            last = exc
            if not is_lock_error(exc) or attempt >= attempts:
                raise
            time.sleep(delay)
            delay = min(float(max_delay), delay * 1.8)
    raise last  # pragma: no cover
