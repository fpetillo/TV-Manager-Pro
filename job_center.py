from __future__ import annotations

import threading
import traceback
import uuid
import json
import sqlite3
from pathlib import Path
from contextlib import closing
from datetime import datetime
from typing import Any, Callable

_LOCK = threading.RLock()
_JOBS: dict[str, dict[str, Any]] = {}
_MAX_JOBS = 500
_SLOTS = threading.Condition()
_RUNNING_COUNT = 0
_STORE = None
_MAX_PENDING = 256

TERMINAL_STATUSES = {"complete", "error", "cancelled"}


def configure(path):
    """Load history once per serving process; interrupted work must be reviewed before retry."""
    global _STORE
    with _LOCK:
        _STORE=Path(path)
        _STORE.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(_STORE,timeout=15)) as con:
            con.execute('PRAGMA journal_mode=WAL')
            con.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,payload TEXT NOT NULL,updated TEXT NOT NULL)')
            rows=con.execute('SELECT payload FROM jobs ORDER BY updated DESC LIMIT 500').fetchall()
            _JOBS.clear()
            for (payload,) in reversed(rows):
                job=json.loads(payload)
                if job.get('status') not in TERMINAL_STATUSES:
                    job.update(status='error',stage='Interrupted by restart',completed_at=_now(),updated_at=_now(),
                        message='TV Manager restarted before this job finished. Review its result and the downloader/library before starting it again.',interrupted=True)
                _JOBS[job['job_id']]=job
                con.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?)',(job['job_id'],json.dumps(job,default=str),job['updated_at']))
            con.commit()


def _persist(job):
    if _STORE is None:return
    with closing(sqlite3.connect(_STORE,timeout=15)) as con:
        con.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?)',(job['job_id'],json.dumps(job,default=str),job.get('updated_at',_now())))
        con.execute('DELETE FROM jobs WHERE id NOT IN (SELECT id FROM jobs ORDER BY updated DESC LIMIT 500)')
        con.commit()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_job(kind: str, *, stage: str = "Queued", message: str = "Queued.", total: int = 0, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "job_id": job_id,
        "kind": kind,
        "status": "queued",
        "stage": stage,
        "message": message,
        "percent": 0,
        "total": int(total or 0),
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
        "result": None,
        "meta": dict(meta or {}),
        "created_at": _now(),
        "updated_at": _now(),
        "completed_at": None,
    }
    with _LOCK:
        if sum(j.get('status') not in TERMINAL_STATUSES for j in _JOBS.values())>=_MAX_PENDING:
            raise ValueError('The background queue is full. Wait for jobs to finish before starting more.')
        _persist(job)
        _JOBS[job_id] = job
        _prune_locked()
        return dict(job)


def update_job(job_id: str, **updates: Any) -> dict[str, Any]:
    with _LOCK:
        job = _JOBS.setdefault(job_id, {"job_id": job_id, "created_at": _now()})
        if "percent" in updates:
            try:
                updates["percent"] = max(0, min(100, int(float(updates["percent"]))))
            except Exception:
                updates["percent"] = 0
        job.update(updates)
        job["updated_at"] = _now()
        if job.get("status") in TERMINAL_STATUSES and not job.get("completed_at"):
            job["completed_at"] = _now()
        _persist(job)
        return dict(job)


def append_error(job_id: str, error: dict[str, Any] | str, *, limit: int = 50) -> dict[str, Any]:
    with _LOCK:
        job = _JOBS.setdefault(job_id, {"job_id": job_id, "created_at": _now()})
        errors = list(job.get("errors") or [])
        errors.append({"error": str(error)} if not isinstance(error, dict) else error)
        job["errors"] = errors[-max(1, limit):]
        job["updated_at"] = _now()
        _persist(job)
        return dict(job)


def get_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def list_jobs(kind: str | None = None, *, limit: int = 50) -> list[dict[str, Any]]:
    with _LOCK:
        jobs = list(_JOBS.values())
    if kind:
        jobs = [j for j in jobs if j.get("kind") == kind]
    jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    return [dict(j) for j in jobs[: max(1, int(limit or 50))]]


def worker_limit():
    try:
        import engine
        return max(1, min(16, int(engine.get_setting('TVManager', 'background_worker_limit', '4'))))
    except (ValueError, TypeError):
        return 4


def cancel_requested(job_id):
    return bool((get_job(job_id) or {}).get('cancel_requested'))


def request_cancel(job_id):
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            raise ValueError('Job not found')
        if not job.get('meta', {}).get('cancelable'):
            raise ValueError('This job cannot be stopped safely from this screen.')
        if job.get('status') not in TERMINAL_STATUSES:
            job['cancel_requested'] = True
            job['message'] = 'Stop requested. Waiting for the current episode to finish.'
            job['updated_at'] = _now()
            _persist(job)
        return dict(job)


def run_background(kind: str, worker: Callable[[str], Any], *, stage: str = "Queued", message: str = "Queued.", total: int = 0, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    job = create_job(kind, stage=stage, message=message, total=total, meta=meta)
    job_id = job["job_id"]

    def _runner() -> None:
        global _RUNNING_COUNT
        try:
            limit = worker_limit()
            with _SLOTS:
                while _RUNNING_COUNT >= limit and not cancel_requested(job_id):
                    _SLOTS.wait(0.5)
                if cancel_requested(job_id):
                    update_job(job_id, status='cancelled', stage='Stopped', message='Stopped before starting.')
                    return
                _RUNNING_COUNT += 1
            try:
                update_job(job_id, status="running", stage=stage, message=message, percent=0)
                result = worker(job_id)
                final = get_job(job_id) or {}
                if final.get("status") not in TERMINAL_STATUSES:
                    update_job(job_id, status="complete", stage="Complete", message="Complete.", percent=100, result=result)
            finally:
                with _SLOTS:
                    _RUNNING_COUNT -= 1
                    _SLOTS.notify_all()
        except Exception as exc:
            append_error(job_id, {"error": str(exc), "traceback": traceback.format_exc()[-4000:]})
            update_job(job_id, status="error", stage="Error", message=str(exc), percent=(get_job(job_id) or {}).get("percent", 0))

    thread = threading.Thread(target=_runner, daemon=True, name=f"tvmanager-{kind}-{job_id}")
    thread.start()
    return get_job(job_id) or job


def _prune_locked() -> None:
    if len(_JOBS) <= _MAX_JOBS:
        return
    ordered = sorted(_JOBS.items(), key=lambda item: item[1].get("created_at", ""))
    for job_id, job in ordered:
        if len(_JOBS) <= _MAX_JOBS:
            break
        if job.get("status") in TERMINAL_STATUSES:
            _JOBS.pop(job_id, None)
