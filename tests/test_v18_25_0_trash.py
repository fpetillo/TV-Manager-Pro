"""v18.25.0: managed trash on the media share, with restore and Empty trash."""
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCENARIO = textwrap.dedent(r'''
    import json, os, sys
    from pathlib import Path
    import app, engine, lifecycle, library_maintenance, completion, trash
    client = app.app.test_client()
    lib = Path(sys.argv[1]) / "Library"
    season = lib / "Show" / "Season 01"
    season.mkdir(parents=True)
    files = {n: season / f"Show - S01E0{n}.mkv" for n in range(1, 6)}
    for n, p in files.items():
        p.write_bytes(b"x" * (n * 1000))
    engine.set_setting("General", "root_dirs", "0|" + str(lib))
    with engine.cx() as c:
        c.execute("INSERT INTO shows(id,name,location) VALUES(1,'Show',?)", (str(lib / "Show"),))
        for n, p in files.items():
            c.execute("INSERT INTO episodes(id,show_id,season,episode,status,location,file_size,quality,release_name,airdate) VALUES(?,1,1,?,'Downloaded',?,?,'720p',?,?)",
                      (n, n, str(p), n * 1000, f"Show.S01E0{n}.720p", f"2020-01-0{n}"))
        c.commit()
    out = {}
    trash_root = lib / ".tvmanager-trash"

    # 1. Upgrade: the old file goes to trash on the share (a rename), recorded with its rollback link.
    with engine.cx() as c:
        ep = dict(c.execute("SELECT * FROM episodes WHERE id=1").fetchone())
    staged = lifecycle.stage_replacement(ep, str(season / "incoming.mkv"), new_release="Show.S01E01.1080p", new_quality="1080p", force=True)
    out["upgrade_in_share_trash"] = Path(staged["trash_path"]).is_relative_to(trash_root / "upgrades")
    out["upgrade_original_gone"] = not files[1].exists()
    out["markers"] = sorted(p.name for p in trash_root.iterdir() if p.is_file())

    # 2. Duplicate cleanup and retention also land in the share's trash.
    dup = library_maintenance.apply_duplicate_cleanup(engine.DB, trash_root=Path(sys.argv[1]) / "fallback",
                                                      actions=[{"source_path": str(files[2]), "fingerprint": "f"}])
    out["dup_in_share_trash"] = Path(dup["results"][0]["trash_path"]).is_relative_to(trash_root / "duplicates")
    with engine.cx() as c:
        c.execute("INSERT INTO retention_policies(id,name,keep_latest,keep_days,keep_watched,enabled) VALUES(1,'Keep 2',2,0,0,1)")
        c.execute("UPDATE shows SET retention_policy_id=1 WHERE id=1")
        c.commit()
    ret = completion.retention_apply(1)
    out["retention_deleted"] = ret["deleted"]

    api = client.get("/api/trash").get_json()
    out["summary"] = {k: v["count"] for k, v in api["categories"].items()}
    out["locations"] = api["locations"]
    items = {i["category"]: i for i in api["items"]}

    # 3. Restore: the upgrade goes back through rollback; a retention file goes back and the episode follows.
    r = client.post(f"/api/trash/restore/{items['upgrades']['id']}").get_json()
    out["upgrade_restored"] = [r.get("via"), files[1].exists()]
    with engine.cx() as c:
        ret_item = c.execute("SELECT * FROM trash_items WHERE category='retention' AND restored_at IS NULL ORDER BY id LIMIT 1").fetchone()
    client.post(f"/api/trash/restore/{ret_item['id']}")
    with engine.cx() as c:
        ep = c.execute("SELECT status, location FROM episodes WHERE id=?", (ret_item["episode_id"],)).fetchone()
    out["retention_restored"] = [ep["status"], Path(ep["location"]).exists()]
    out["restore_twice"] = client.post(f"/api/trash/restore/{ret_item['id']}").status_code

    # 4. Empty: selected, then everything; folders are cleaned up.
    left = client.get("/api/trash").get_json()["items"]
    sel = client.post("/api/trash/empty", json={"mode": "selected", "ids": [left[0]["id"]]}).get_json()
    out["selected"] = [sel["deleted"], Path(left[0]["trash_path"]).exists()]
    before = client.get("/api/trash").get_json()["total_count"]
    allr = client.post("/api/trash/empty", json={"mode": "older", "days": 0}).get_json()
    out["emptied_all"] = [before, allr["deleted"], client.get("/api/trash").get_json()["total_count"]]
    out["trash_files_left"] = [str(p) for p in trash_root.rglob("*") if p.is_file() and p.name not in trash.IGNORE_MARKERS]

    # 5. Old trash on the server's own drive is listed and can be emptied.
    legacy = trash.LEGACY / "upgrades" / "20240101-000000"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "old.mkv").write_bytes(b"y" * 5000)
    s = client.get("/api/trash").get_json()["legacy"]
    out["legacy_listed"] = [s["count"], s["bytes"]]
    lr = client.post("/api/trash/empty", json={"mode": "legacy"}).get_json()
    out["legacy_emptied"] = [lr["legacy_deleted"], (legacy / "old.mkv").exists()]

    # 6. Settings: fixed folder and auto-empty; bad values refused.
    fixed = Path(sys.argv[1]) / "FixedTrash"
    out["settings_ok"] = client.post("/api/trash/settings", json={"trash_folder": str(fixed), "trash_auto_empty_days": 30}).status_code
    moved = trash.move_to_trash(files[5], "duplicates")
    out["fixed_used"] = Path(moved).is_relative_to(fixed)
    out["bad"] = [client.post("/api/trash/settings", json={"trash_auto_empty_days": -1}).status_code,
                  client.post("/api/trash/settings", json={"trash_folder": "relative/path"}).status_code,
                  client.post("/api/trash/empty", json={"mode": "nope"}).status_code,
                  client.post("/api/trash/empty", json={"mode": "older", "days": "x"}).status_code]
    out["auto_empty_recent_kept"] = trash.auto_empty(engine.get_setting)["deleted"]
    out["page"] = client.get("/trash").status_code
    out["nav"] = 'href="/trash"' in client.get("/dashboard").get_data(as_text=True)
    print(json.dumps(out, default=str))
''')


def test_trash_on_share_restore_and_empty():
    with tempfile.TemporaryDirectory() as tmp:
        app_dir = Path(tmp) / "app"
        shutil.copytree(ROOT, app_dir, ignore=shutil.ignore_patterns(
            ".git", "tests", "*.db*", "managed_trash", "logs", ".runtime", "__pycache__", "imports", "backups"))
        (app_dir / "scenario.py").write_text(SCENARIO, encoding="utf-8")
        r = subprocess.run([sys.executable, "scenario.py", tmp], cwd=app_dir, capture_output=True, text=True, timeout=240)
        assert r.returncode == 0, r.stderr[-3000:]
        out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["upgrade_in_share_trash"] and out["upgrade_original_gone"]
    assert out["markers"] == [".ignore", ".nomedia", ".plexignore"]  # media servers skip the trash folder
    assert out["dup_in_share_trash"]
    # Keep latest 2 by air date: E05 and E04 stay; E03 goes (E01 and E02 were already moved away).
    assert out["retention_deleted"] == 1
    assert out["summary"] == {"upgrades": 1, "rollback_replaced": 0, "duplicates": 1, "retention": 1}
    assert out["locations"][0].endswith(".tvmanager-trash")
    assert out["upgrade_restored"] == ["upgrade rollback", True]
    assert out["retention_restored"] == ["Downloaded", True]
    assert out["restore_twice"] == 400
    assert out["selected"] == [1, False]
    assert out["emptied_all"][1] == out["emptied_all"][0] and out["emptied_all"][2] == 0
    assert out["trash_files_left"] == []
    assert out["legacy_listed"] == [1, 5000]
    assert out["legacy_emptied"] == [1, False]
    assert out["settings_ok"] == 200 and out["fixed_used"] is True
    assert out["bad"] == [400, 400, 400, 400]
    assert out["auto_empty_recent_kept"] == 0
    assert out["page"] == 200 and out["nav"] is True
