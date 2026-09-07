from __future__ import annotations

import threading
import traceback
import uuid
from datetime import datetime
from typing import Any, Callable

_LOCK = threading.RLock()
_JOBS: dict[str, dict[str, Any]] = {}
_MAX_JOBS = 100

TERMINAL_STATUSES = {"complete", "error", "cancelled"}


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
        return dict(job)


def append_error(job_id: str, error: dict[str, Any] | str, *, limit: int = 50) -> dict[str, Any]:
    with _LOCK:
        job = _JOBS.setdefault(job_id, {"job_id": job_id, "created_at": _now()})
        errors = list(job.get("errors") or [])
        errors.append({"error": str(error)} if not isinstance(error, dict) else error)
        job["errors"] = errors[-max(1, limit):]
        job["updated_at"] = _now()
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


def run_background(kind: str, worker: Callable[[str], Any], *, stage: str = "Queued", message: str = "Queued.", total: int = 0, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    job = create_job(kind, stage=stage, message=message, total=total, meta=meta)
    job_id = job["job_id"]

    def _runner() -> None:
        update_job(job_id, status="running", stage=stage, message=message, percent=0)
        try:
            result = worker(job_id)
            final = get_job(job_id) or {}
            if final.get("status") not in TERMINAL_STATUSES:
                update_job(job_id, status="complete", stage="Complete", message="Complete.", percent=100, result=result)
        except Exception as exc:  # noqa: BLE001 - operator job boundary
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
