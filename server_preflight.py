#!/usr/bin/env python3
"""TV Manager server replacement preflight checks.

Runs read-only checks before replacing a SickChill server. It does not modify
SickChill, TV Manager, or media files. A JSON report is written to diagnostics/.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def check_port(host: str, port: int) -> dict:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.5)
    try:
        result = s.connect_ex((host, port))
        return {"host": host, "port": port, "available": result != 0, "connect_ex": result}
    finally:
        s.close()


def sqlite_summary(db_path: Path) -> dict:
    if not db_path.exists():
        return {"path": str(db_path), "exists": False}
    out = {"path": str(db_path), "exists": True, "size": db_path.stat().st_size}
    try:
        with sqlite3.connect(db_path) as con:
            con.row_factory = sqlite3.Row
            tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            out["tables"] = tables
            out["quick_check"] = con.execute("PRAGMA quick_check").fetchone()[0]
            for candidate in ("tv_shows", "shows", "tv_episodes", "episodes"):
                if candidate in tables:
                    out[f"{candidate}_count"] = con.execute(f'SELECT COUNT(*) FROM "{candidate}"').fetchone()[0]
    except Exception as exc:
        out["error"] = str(exc)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="TV Manager SickChill replacement preflight")
    parser.add_argument("--sickchill-db", default="", help="Path to SickChill sickbeard.db")
    parser.add_argument("--tvmanager-db", default="tvmanager.db", help="Path to TV Manager tvmanager.db")
    parser.add_argument("--media-root", action="append", default=[], help="Media root path to verify; may be repeated")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    diagnostics = base / "diagnostics"
    diagnostics.mkdir(exist_ok=True)
    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "base": str(base),
        "python": sys.version,
        "platform": platform.platform(),
        "version": (base / "VERSION").read_text(encoding="utf-8").strip() if (base / "VERSION").exists() else "unknown",
        "commands": {
            "python": shutil.which("python") or shutil.which("python3"),
            "git": shutil.which("git"),
        },
        "port": check_port(args.host, args.port),
        "tvmanager_db": sqlite_summary(Path(args.tvmanager_db)),
        "sickchill_db": sqlite_summary(Path(args.sickchill_db)) if args.sickchill_db else {"provided": False},
        "media_roots": [],
        "recommendations": [],
    }
    for root in args.media_root:
        p = Path(root)
        entry = {"path": str(p), "exists": p.exists(), "is_dir": p.is_dir(), "readable": os.access(p, os.R_OK), "writable": os.access(p, os.W_OK)}
        report["media_roots"].append(entry)
    if not report["port"]["available"]:
        report["recommendations"].append(f"Port {args.port} is already in use. Stop SickChill or choose another TV Manager port for the first test run.")
    if args.sickchill_db and not Path(args.sickchill_db).exists():
        report["recommendations"].append("SickChill database path was supplied but does not exist.")
    if not report["media_roots"]:
        report["recommendations"].append("Provide at least one --media-root path during final replacement planning.")

    out = diagnostics / "server-preflight.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nPreflight report written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
