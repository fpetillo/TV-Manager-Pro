"""Managed trash (v18.25.0): one index for every file TV Manager sets aside, kept on the media share.

Files TV Manager removes or replaces are moved, not deleted:
  upgrades           the previous file when a better copy (or "Replace anyway") replaces it
  rollback_replaced  the newer file when an upgrade is rolled back
  duplicates         copies removed by Library Health duplicate cleanup
  retention          files removed by a retention policy

Where trash lives: in a ``.tvmanager-trash`` folder at the top of the library folder that holds
the file (for example ``\\\\server\\Media\\TV\\.tvmanager-trash``), so a move is a rename on the
same share: instant, and nothing is copied onto the server's own drive. The setting
TVManager/trash_folder overrides this with one fixed folder. Files outside every library folder
fall back to the old ``managed_trash`` folder in the installation.

Everything in trash can be restored to where it came from or deleted for good (Empty trash),
and TVManager/trash_auto_empty_days > 0 empties older items every night.
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import app_paths
import dbcore

BASE = app_paths.application_root()
DB = BASE / "tvmanager.db"
LEGACY = BASE / "managed_trash"
FOLDER_NAME = ".tvmanager-trash"
CATEGORIES = {
    "upgrades": "Replaced by an upgrade",
    "rollback_replaced": "Removed by an upgrade rollback",
    "duplicates": "Duplicate cleanup",
    "retention": "Retention policy",
}


_SCHEMA = ["""
        CREATE TABLE IF NOT EXISTS trash_items(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          category TEXT NOT NULL,
          original_path TEXT NOT NULL,
          trash_path TEXT NOT NULL,
          size INTEGER DEFAULT 0,
          episode_id INTEGER,
          show_id INTEGER,
          reason TEXT,
          ref TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          restored_at TEXT,
          deleted_at TEXT
        )""",
    "CREATE INDEX IF NOT EXISTS idx_trash_items_open ON trash_items(deleted_at, restored_at, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_trash_items_path ON trash_items(trash_path)",
]


def init(conn) -> None:
    # Plain execute (not executescript, which would commit the caller's open transaction).
    for statement in _SCHEMA:
        conn.execute(statement)


def _cx(conn=None):
    return conn if conn is not None else dbcore.connect(DB)


def _setting(conn, name, default=""):
    try:
        row = conn.execute("SELECT value FROM settings WHERE lower(section)='tvmanager' AND lower(name)=lower(?)", (name,)).fetchone()
    except Exception:  # noqa: BLE001
        return default
    return default if not row or row[0] in (None, "") else row[0]


def trash_root_for(path, conn, fallback=None) -> Path:
    """The trash folder for a file: fixed folder if configured, else the top of its library folder."""
    fixed = str(_setting(conn, "trash_folder", "")).strip()
    if fixed:
        return Path(fixed)
    try:
        import library_locations
        roots, _default = library_locations.read_roots(conn)
        # Longest matching root first, so nested library folders pick the closest one.
        for root in sorted(roots, key=len, reverse=True):
            if library_locations.contains(root, str(path)):
                return Path(root) / FOLDER_NAME
    except Exception:  # noqa: BLE001
        pass
    return Path(fallback) if fallback else LEGACY


# Media servers scan the library share. These markers keep them out of the trash folder:
# Plex (.plexignore), Jellyfin/Emby (.ignore) and Kodi (.nomedia).
IGNORE_MARKERS = {".plexignore": "# TV Manager trash: not part of the library\n*\n", ".ignore": "", ".nomedia": ""}


def _mark_ignored(root: Path) -> None:
    if root == LEGACY:
        return
    for name, text in IGNORE_MARKERS.items():
        marker = root / name
        try:
            if not marker.exists():
                marker.write_text(text, encoding="utf-8")
        except OSError:
            pass


def _unique(target: Path) -> Path:
    if not target.exists():
        return target
    n = 1
    while True:
        candidate = target.with_name(f"{target.stem}-{n}{target.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def move_to_trash(src, category, *, episode_id=None, show_id=None, reason="", ref=None, conn=None, fallback_root=None) -> str:
    """Move one file into trash, record it, and return the new path.

    Pass ``conn`` when the caller already has an open write transaction, so the record is written
    on the same connection (a second connection would wait for the first to finish).
    """
    if category not in CATEGORIES:
        raise ValueError(f"Unknown trash category: {category}")
    src = Path(src)
    own = conn is None
    c = _cx(conn)
    try:
        init(c)
        root = trash_root_for(src, c, fallback_root)
        folder = root / category / datetime.now().strftime("%Y%m%d-%H%M%S")
        folder.mkdir(parents=True, exist_ok=True)
        _mark_ignored(root)
        target = _unique(folder / src.name)
        size = src.stat().st_size if src.is_file() else 0
        shutil.move(str(src), str(target))  # a rename when trash is on the same share
        c.execute("""INSERT INTO trash_items(category,original_path,trash_path,size,episode_id,show_id,reason,ref)
                     VALUES(?,?,?,?,?,?,?,?)""",
                  (category, str(src), str(target), size, episode_id, show_id, reason or CATEGORIES[category], ref))
        if own:
            c.commit()
        return str(target)
    finally:
        if own:
            c.close()


def set_ref(trash_path, ref, conn=None) -> None:
    own = conn is None
    c = _cx(conn)
    try:
        c.execute("UPDATE trash_items SET ref=? WHERE trash_path=? AND deleted_at IS NULL", (ref, str(trash_path)))
        if own:
            c.commit()
    finally:
        if own:
            c.close()


def mark_restored(trash_path, conn=None) -> None:
    own = conn is None
    c = _cx(conn)
    try:
        c.execute("UPDATE trash_items SET restored_at=CURRENT_TIMESTAMP WHERE trash_path=? AND restored_at IS NULL", (str(trash_path),))
        if own:
            c.commit()
    finally:
        if own:
            c.close()


# ------------------------------------------------------------------ reading
def _legacy_files() -> list[Path]:
    if not LEGACY.exists():
        return []
    out = []
    for folder, _dirs, names in os.walk(LEGACY):
        for name in names:
            out.append(Path(folder) / name)
    return out


def summary() -> dict[str, Any]:
    with dbcore.connect(DB, readonly=True) as c:
        rows = c.execute("""SELECT category, COUNT(*) n, COALESCE(SUM(size),0) bytes, MIN(created_at) oldest
                            FROM trash_items WHERE deleted_at IS NULL AND restored_at IS NULL GROUP BY category""").fetchall()
        indexed = {r[0] for r in c.execute("SELECT trash_path FROM trash_items WHERE deleted_at IS NULL AND restored_at IS NULL")}
        settings = {"trash_folder": _setting(c, "trash_folder", ""),
                    "trash_auto_empty_days": int(str(_setting(c, "trash_auto_empty_days", "0")).strip() or 0)}
        roots = []
        try:
            import library_locations
            roots = [str(Path(r) / FOLDER_NAME) for r in library_locations.read_roots(c)[0]]
        except Exception:  # noqa: BLE001
            pass
    categories = {k: {"label": v, "count": 0, "bytes": 0, "oldest": None} for k, v in CATEGORIES.items()}
    for r in rows:
        categories.setdefault(r["category"], {"label": r["category"], "count": 0, "bytes": 0, "oldest": None})
        categories[r["category"]].update(count=r["n"], bytes=r["bytes"], oldest=r["oldest"])
    # Files from before 18.25.0 sit in managed_trash on the server's own drive without an index entry.
    legacy = [p for p in _legacy_files() if str(p) not in indexed]
    legacy_bytes = 0
    for p in legacy:
        try:
            legacy_bytes += p.stat().st_size
        except OSError:
            pass
    return {
        "ok": True,
        "categories": categories,
        "total_count": sum(v["count"] for v in categories.values()),
        "total_bytes": sum(v["bytes"] for v in categories.values()),
        "legacy": {"path": str(LEGACY), "count": len(legacy), "bytes": legacy_bytes},
        "settings": settings,
        "locations": [settings["trash_folder"]] if settings["trash_folder"] else roots,
    }


def items(limit=500, category=None) -> list[dict[str, Any]]:
    sql = """SELECT t.*, s.name show_name, e.season, e.episode FROM trash_items t
             LEFT JOIN episodes e ON e.id=t.episode_id
             LEFT JOIN shows s ON s.id=COALESCE(t.show_id, e.show_id)
             WHERE t.deleted_at IS NULL AND t.restored_at IS NULL"""
    params: list[Any] = []
    if category:
        sql += " AND t.category=?"
        params.append(category)
    sql += " ORDER BY t.created_at DESC, t.id DESC LIMIT ?"
    params.append(max(1, min(5000, int(limit))))
    with dbcore.connect(DB, readonly=True) as c:
        return [dict(r) for r in c.execute(sql, params)]


# ------------------------------------------------------------------ restore and empty
def restore(item_id: int) -> dict[str, Any]:
    with dbcore.connect(DB, readonly=True) as c:
        r = c.execute("SELECT * FROM trash_items WHERE id=?", (int(item_id),)).fetchone()
    if not r or r["deleted_at"] or r["restored_at"]:
        raise ValueError("That item is no longer in trash.")
    if r["category"] == "upgrades" and str(r["ref"] or "").startswith("upgrade_replacements:"):
        # Upgrades go back through the normal rollback so the episode record follows.
        import lifecycle
        out = lifecycle.rollback_replacement(int(str(r["ref"]).split(":", 1)[1]))
        return {"ok": True, "restored": out.get("restored"), "via": "upgrade rollback"}
    trash_path, original = Path(r["trash_path"]), Path(r["original_path"])
    if not trash_path.exists():
        raise ValueError("The file is no longer in the trash folder.")
    if original.exists():
        raise ValueError(f"A file already exists at {original}. Move or remove it first.")
    original.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(trash_path), str(original))
    with dbcore.connect(DB) as c:
        c.execute("UPDATE trash_items SET restored_at=CURRENT_TIMESTAMP WHERE id=?", (r["id"],))
        if r["episode_id"] and r["category"] == "retention":
            c.execute("""UPDATE episodes SET location=?, file_size=?, status='Downloaded'
                         WHERE id=? AND TRIM(COALESCE(location,''))=''""", (str(original), r["size"], r["episode_id"]))
        c.commit()
    return {"ok": True, "restored": str(original)}


def _remove_empty_dirs(start: Path, stop_at: Path) -> None:
    folder = start
    while folder != stop_at and stop_at in folder.parents:
        try:
            folder.rmdir()  # only succeeds when empty
        except OSError:
            return
        folder = folder.parent


def empty(*, older_than_days: int | None = None, item_ids: list[int] | None = None,
          category: str | None = None, include_legacy: bool = False) -> dict[str, Any]:
    """Delete trashed files for good. Returns counts and bytes freed."""
    where = ["deleted_at IS NULL", "restored_at IS NULL"]
    params: list[Any] = []
    if item_ids is not None:
        ids = [int(x) for x in item_ids] or [-1]   # an empty selection matches nothing
        where.append(f"id IN ({','.join('?' for _ in ids)})")
        params += ids
    if older_than_days is not None:
        where.append("created_at <= datetime('now', ?)")
        params.append(f"-{max(0, int(older_than_days))} days")
    if category:
        where.append("category=?")
        params.append(category)
    with dbcore.connect(DB, readonly=True) as c:
        rows = c.execute(f"SELECT id, trash_path, size FROM trash_items WHERE {' AND '.join(where)}", params).fetchall()
    deleted = missing = freed = 0
    errors: list[str] = []
    done: list[int] = []
    for r in rows:
        p = Path(r["trash_path"])
        try:
            if p.exists():
                p.unlink()
                freed += int(r["size"] or 0)
                deleted += 1
            else:
                missing += 1
            done.append(r["id"])
            parts = [x for x in p.parents if x.name == FOLDER_NAME or x == LEGACY]
            if parts:
                _remove_empty_dirs(p.parent, parts[0])
        except OSError as exc:
            errors.append(f"{p}: {exc}")
    if done:
        with dbcore.connect(DB) as c:
            for i in range(0, len(done), 500):
                chunk = done[i:i + 500]
                c.execute(f"UPDATE trash_items SET deleted_at=CURRENT_TIMESTAMP WHERE id IN ({','.join('?' for _ in chunk)})", chunk)
            c.commit()
    legacy_deleted = legacy_bytes = 0
    if include_legacy:
        cutoff = None
        if older_than_days is not None:
            cutoff = datetime.now().timestamp() - max(0, int(older_than_days)) * 86400
        for p in _legacy_files():
            try:
                st = p.stat()
                if cutoff is not None and st.st_mtime > cutoff:
                    continue
                p.unlink()
                legacy_deleted += 1
                legacy_bytes += st.st_size
                _remove_empty_dirs(p.parent, LEGACY)
            except OSError as exc:
                errors.append(f"{p}: {exc}")
    return {"ok": not errors, "deleted": deleted + legacy_deleted, "bytes": freed + legacy_bytes,
            "missing": missing, "legacy_deleted": legacy_deleted, "errors": errors[:20]}


def save_settings(values: dict[str, Any]) -> dict[str, Any]:
    import engine
    if "trash_auto_empty_days" in values:
        try:
            days = int(str(values["trash_auto_empty_days"]).strip() or 0)
        except ValueError:
            raise ValueError("Empty automatically after must be a number of days (0 = never).") from None
        if not 0 <= days <= 3650:
            raise ValueError("Empty automatically after must be between 0 and 3650 days.")
        engine.set_setting("TVManager", "trash_auto_empty_days", str(days))
    if "trash_folder" in values:
        folder = str(values["trash_folder"] or "").strip()
        if folder:
            import library_locations
            folder = library_locations.validate_root(folder)
        engine.set_setting("TVManager", "trash_folder", folder)
    return summary()


def auto_empty(get_setting) -> dict[str, Any] | None:
    try:
        days = int(str(get_setting("TVManager", "trash_auto_empty_days", "0")).strip() or 0)
    except ValueError:
        days = 0
    if days <= 0:
        return None
    return empty(older_than_days=days, include_legacy=True)
