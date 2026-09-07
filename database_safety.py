from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
DB = BASE / "tvmanager.db"
BACKUPS = BASE / "backups"
SAFE_BACKUPS = BACKUPS / "safe"
CONFIG_BACKUPS = BACKUPS / "config"
MANIFEST = BACKUPS / "db-backup-manifest.json"

SECRET_NAMES = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASS", "API", "AUTH")
CONFIG_FILES = (".env", "settings.ini", "config.ini", "sickbeard.ini", "VERSION")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest_records() -> list[dict[str, Any]]:
    if not MANIFEST.exists():
        return []
    try:
        raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return list(raw.get("backups") or [])
        if isinstance(raw, list):
            return list(raw)
    except Exception:
        return []
    return []


def _write_manifest(records: list[dict[str, Any]]) -> None:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": _now(), "backups": records[-500:]}
    MANIFEST.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def record_backup(record: dict[str, Any]) -> dict[str, Any]:
    records = _manifest_records()
    records.append(record)
    _write_manifest(records)
    return record


def quick_check(db_path: str | Path = DB) -> dict[str, Any]:
    db_path = Path(db_path)
    out = {
        "database": str(db_path),
        "exists": db_path.exists(),
        "size": db_path.stat().st_size if db_path.exists() else 0,
        "ok": True,
        "quick_check": "missing" if not db_path.exists() else None,
        "error": None,
        "checked_at": _now(),
    }
    if not db_path.exists() or out["size"] == 0:
        return out
    con = None
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
        row = con.execute("PRAGMA quick_check").fetchone()
        out["quick_check"] = row[0] if row else "no result"
        out["ok"] = str(out["quick_check"]).lower() == "ok"
    except sqlite3.DatabaseError as exc:
        out["ok"] = False
        out["quick_check"] = "database_error"
        out["error"] = str(exc)
    finally:
        if con is not None:
            con.close()
    return out


def backup_database(db_path: str | Path = DB, *, reason: str = "manual", retention: int = 25) -> dict[str, Any]:
    """Create a verified online SQLite backup without copying a hot DB file.

    sqlite3.Connection.backup() takes a consistent snapshot, which protects the
    show library database better than raw Copy-Item/robocopy while TV Manager is
    running or after WAL mode has been used.
    """
    db_path = Path(db_path)
    SAFE_BACKUPS.mkdir(parents=True, exist_ok=True)
    ts = _stamp()
    target = SAFE_BACKUPS / f"tvmanager-{reason}-{ts}.db"
    record: dict[str, Any] = {
        "timestamp": _now(),
        "reason": reason,
        "source": str(db_path),
        "backup": str(target),
        "method": "sqlite_backup_api",
        "ok": False,
        "size": 0,
        "sha256": None,
        "quick_check": None,
        "error": None,
    }
    if not db_path.exists():
        record.update({"ok": True, "quick_check": "source_missing", "error": None})
        return record_backup(record)

    source = dest = None
    try:
        source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
        dest = sqlite3.connect(target)
        source.backup(dest, pages=1000, sleep=0.05)
        dest.commit()
        dest.close(); dest = None
        source.close(); source = None
        check = quick_check(target)
        record.update({
            "ok": bool(check.get("ok")),
            "quick_check": check.get("quick_check"),
            "error": check.get("error"),
            "size": target.stat().st_size if target.exists() else 0,
            "sha256": _sha256(target) if target.exists() else None,
        })
        if record["sha256"]:
            (target.with_suffix(target.suffix + ".sha256")).write_text(record["sha256"] + "  " + target.name + "\n", encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        record["error"] = str(exc)
        record["method"] = "sqlite_backup_api_failed"
        # Preserve the exact bytes for later external recovery, but mark it bad.
        try:
            raw = SAFE_BACKUPS / f"tvmanager-preserved-unverified-{reason}-{ts}.db"
            shutil.copy2(db_path, raw)
            record["preserved_unverified_copy"] = str(raw)
        except Exception as copy_exc:  # noqa: BLE001
            record["preserve_error"] = str(copy_exc)
    finally:
        for con in (dest, source):
            try:
                if con is not None:
                    con.close()
            except Exception:
                pass
    record_backup(record)
    prune_backups(retention=retention)
    return record


def _redact_env_line(line: str) -> str:
    if "=" not in line or line.lstrip().startswith("#"):
        return line
    name, value = line.split("=", 1)
    upper = name.upper()
    if any(token in upper for token in SECRET_NAMES) and value.strip():
        return f"{name}=<redacted>"
    return line


def backup_config_files(*, reason: str = "manual", include_secrets: bool = False) -> dict[str, Any]:
    CONFIG_BACKUPS.mkdir(parents=True, exist_ok=True)
    target_dir = CONFIG_BACKUPS / f"config-{reason}-{_stamp()}"
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, Any]] = []
    for name in CONFIG_FILES:
        src = BASE / name
        if not src.exists() or not src.is_file():
            continue
        if src.name == ".env" and not include_secrets:
            target = target_dir / ".env.redacted.txt"
            lines = [_redact_env_line(x) for x in src.read_text(encoding="utf-8", errors="replace").splitlines()]
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")
            copied.append({"source": str(src), "backup": str(target), "redacted": True, "sha256": _sha256(target)})
        else:
            target = target_dir / src.name
            shutil.copy2(src, target)
            copied.append({"source": str(src), "backup": str(target), "redacted": False, "sha256": _sha256(target)})
    manifest = {"timestamp": _now(), "reason": reason, "include_secrets": include_secrets, "files": copied}
    (target_dir / "config-backup.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"ok": True, "directory": str(target_dir), "files": copied, "count": len(copied)}


def protect_now(*, reason: str = "manual", include_config: bool = True, include_secrets: bool = False) -> dict[str, Any]:
    db = backup_database(reason=reason)
    cfg = backup_config_files(reason=reason, include_secrets=include_secrets) if include_config else {"ok": True, "count": 0, "files": []}
    return {"ok": bool(db.get("ok")) and bool(cfg.get("ok", True)), "database": db, "config": cfg}


def scan_backups() -> dict[str, Any]:
    candidates: list[Path] = []
    for pattern in ("tvmanager*.db", "*.db"):
        candidates.extend(BASE.glob(pattern))
        if BACKUPS.exists():
            candidates.extend(BACKUPS.glob(pattern))
            candidates.extend(BACKUPS.rglob(pattern))
    seen: set[Path] = set()
    results: list[dict[str, Any]] = []
    for path in candidates:
        path = path.resolve()
        if path in seen or not path.exists() or not path.is_file():
            continue
        seen.add(path)
        qc = quick_check(path)
        try:
            mtime = path.stat().st_mtime
            modified = datetime.fromtimestamp(mtime).isoformat(timespec="seconds")
        except Exception:
            modified = None
        results.append({**qc, "path": str(path), "modified_at": modified, "sha256": _sha256(path) if qc.get("ok") else None})
    results.sort(key=lambda x: x.get("modified_at") or "", reverse=True)
    newest_ok = next((r for r in results if r.get("ok") and Path(r.get("path", "")).name != "tvmanager.db"), None)
    return {"ok": True, "count": len(results), "newest_usable_backup": newest_ok, "results": results, "manifest": _manifest_records()[-50:]}


def prune_backups(*, retention: int = 25) -> None:
    retention = max(5, int(retention or 25))
    if not SAFE_BACKUPS.exists():
        return
    dbs = sorted(SAFE_BACKUPS.glob("tvmanager-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in dbs[retention:]:
        try:
            old.unlink()
            sha = old.with_suffix(old.suffix + ".sha256")
            if sha.exists():
                sha.unlink()
        except Exception:
            pass
