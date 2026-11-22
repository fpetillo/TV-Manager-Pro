"""Missing Episode Autopilot (v18.24.0).

One scheduled job that keeps the library complete without manual checking:

1. Checks the download clients for finished, failed and stalled downloads.
2. A failed or stalled download is blocked (its release goes on the failed-release list, so it is
   never grabbed again) and the episode goes back to Wanted, so the next search picks a
   different release. After ``max_attempts`` failed releases the episode is set aside for review.
3. Processes completed downloads into the library (Post Processing).
4. Searches missing episodes and sends the best acceptable release to the download client.

Missing means: aired (air date today or earlier), no file, monitored, not ignored, show not
paused and searchable, no download already active. Episodes that have not aired yet are never
searched or counted as missing. Episodes not yet tried are searched first (newest first), then
the ones searched longest ago; an episode is not searched again within ``retry_hours``.
"""
from __future__ import annotations

import json
import time
from datetime import date
from typing import Any

JOB_NAME = "missing_autopilot"
DEFAULT_INTERVAL_MINUTES = 60

# setting name (section TVManager, prefix autopilot_) -> (default, minimum, maximum)
SETTINGS: dict[str, tuple[int, int, int]] = {
    "enabled": (0, 0, 1),
    "batch_size": (40, 1, 1000),          # episodes searched per run
    "retry_hours": (24, 1, 24 * 60),      # wait before searching the same episode again
    "stall_hours": (12, 1, 24 * 30),      # a download not finished after this long is given up on
    "max_attempts": (5, 1, 100),          # failed releases per episode before it is set aside
    "max_minutes": (30, 1, 24 * 60),      # time limit for one run
    "include_skipped": (1, 0, 1),         # search episodes marked Skipped (common after SickChill import)
    "include_lost_files": (0, 0, 1),      # search Downloaded/Archived episodes whose file is gone
    "postprocess": (1, 0, 1),             # process completed downloads during each run
}


def _engine():
    import engine
    return engine


def get_settings() -> dict[str, int]:
    e = _engine()
    out = {}
    for name, (default, low, high) in SETTINGS.items():
        raw = e.get_setting("TVManager", f"autopilot_{name}", None)
        try:
            value = int(str(raw).strip()) if raw not in (None, "") else default
        except ValueError:
            value = default
        out[name] = max(low, min(high, value))
    return out


def save_settings(values: dict[str, Any]) -> dict[str, Any]:
    e = _engine()
    values = values or {}
    for name, raw in values.items():
        if name == "interval_minutes":
            continue
        if name not in SETTINGS:
            raise ValueError(f"Unknown Autopilot setting: {name}")
        default, low, high = SETTINGS[name]
        if isinstance(raw, bool):
            raw = int(raw)
        try:
            value = int(str(raw).strip())
        except ValueError:
            raise ValueError(f"{name.replace('_', ' ').capitalize()} must be a whole number.") from None
        if not low <= value <= high:
            raise ValueError(f"{name.replace('_', ' ').capitalize()} must be between {low} and {high}.")
        e.set_setting("TVManager", f"autopilot_{name}", str(value))
    if "interval_minutes" in values:
        try:
            minutes = int(str(values["interval_minutes"]).strip())
        except ValueError:
            raise ValueError("Run every must be a number of minutes.") from None
        if not 5 <= minutes <= 7 * 24 * 60:
            raise ValueError("Run every must be between 5 minutes and 7 days.")
        e.update_job(JOB_NAME, interval=minutes)
    if "enabled" in values:
        on = bool(int(values["enabled"]))
        e.update_job(JOB_NAME, enabled=on)
        if on:
            # The scheduler only runs jobs while automation is armed.
            e.set_automation(True)
        e.log("autopilot", "Missing Episode Autopilot turned " + ("on" if on else "off"))
    return status()


def init(conn) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS autopilot_episodes(
          episode_id INTEGER PRIMARY KEY,
          attempts INTEGER DEFAULT 0,
          last_failure TEXT,
          last_failed_at TEXT,
          gave_up_at TEXT
        );
        CREATE TABLE IF NOT EXISTS autopilot_handled_downloads(
          download_id INTEGER PRIMARY KEY,
          handled_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)


# ------------------------------------------------------------------ which episodes
def _status_filter(cfg) -> str:
    statuses = ["wanted", "failed", "unaired", "unknown", "", "snatched", "new"]
    if cfg["include_skipped"]:
        statuses.append("skipped")
    if cfg["include_lost_files"]:
        statuses += ["downloaded", "archived"]
    return "lower(COALESCE(e.status,'')) IN (" + ",".join(f"'{s}'" for s in statuses) + ")"


def _base_where(cfg) -> str:
    e = _engine()
    import episode_dates
    airdate = episode_dates.sql_expr("e.airdate")
    return f"""TRIM(COALESCE(e.location,''))=''
        AND COALESCE(e.monitored,1)=1 AND COALESCE(e.ignored,0)=0 AND lower(COALESCE(e.status,''))<>'ignored'
        AND COALESCE(s.paused,0)=0 AND COALESCE(s.search_enabled,1)=1
        AND {_status_filter(cfg)}
        {e.specials_wanted_sql('e')}
        AND NOT EXISTS (SELECT 1 FROM downloads d WHERE d.episode_id=e.id
                        AND lower(COALESCE(d.status,'')) IN ('queued','downloading','downloaded','importing'))
        AND date({airdate}) IS NOT NULL AND date({airdate})<=date('now','localtime')"""


def eligible_episode_ids(cfg=None, limit=None) -> list[int]:
    """Missing episodes due for a search now, in search order."""
    cfg = cfg or get_settings()
    e = _engine()
    import episode_dates
    limit = cfg["batch_size"] if limit is None else limit
    sql = f"""SELECT e.id FROM episodes e JOIN shows s ON s.id=e.show_id
              LEFT JOIN autopilot_episodes a ON a.episode_id=e.id
              WHERE {_base_where(cfg)}
                AND a.gave_up_at IS NULL
                AND (e.last_search IS NULL OR e.last_search <= datetime('now', ?))
              ORDER BY (e.last_search IS NOT NULL), e.last_search, {episode_dates.sql_expr('e.airdate')} DESC, e.id
              LIMIT ?"""
    with e._read_cx() as c:
        c.create_function("episode_airdate", 1, episode_dates.normalize)
        return [r[0] for r in c.execute(sql, (f"-{cfg['retry_hours']} hours", limit)).fetchall()]


def counts(cfg=None) -> dict[str, int]:
    cfg = cfg or get_settings()
    e = _engine()
    import episode_dates
    airdate = episode_dates.sql_expr("e.airdate")
    with e._read_cx() as c:
        c.create_function("episode_airdate", 1, episode_dates.normalize)
        base = _base_where(cfg)
        missing = c.execute(f"""SELECT COUNT(*) FROM episodes e JOIN shows s ON s.id=e.show_id
                                LEFT JOIN autopilot_episodes a ON a.episode_id=e.id
                                WHERE {base} AND a.gave_up_at IS NULL""").fetchone()[0]
        due = c.execute(f"""SELECT COUNT(*) FROM episodes e JOIN shows s ON s.id=e.show_id
                            LEFT JOIN autopilot_episodes a ON a.episode_id=e.id
                            WHERE {base} AND a.gave_up_at IS NULL
                              AND (e.last_search IS NULL OR e.last_search <= datetime('now', ?))""",
                         (f"-{cfg['retry_hours']} hours",)).fetchone()[0]
        not_aired = c.execute(f"""SELECT COUNT(*) FROM episodes e JOIN shows s ON s.id=e.show_id
                                  WHERE TRIM(COALESCE(e.location,''))='' AND COALESCE(e.ignored,0)=0
                                    AND lower(COALESCE(e.status,''))<>'ignored' AND COALESCE(e.monitored,1)=1
                                    {e.specials_wanted_sql('e')}
                                    AND date({airdate})>date('now','localtime')""").fetchone()[0]
        downloading = c.execute("""SELECT COUNT(*) FROM downloads
                                   WHERE lower(COALESCE(status,'')) IN ('queued','downloading','downloaded','importing')""").fetchone()[0]
        set_aside = c.execute("SELECT COUNT(*) FROM autopilot_episodes WHERE gave_up_at IS NOT NULL").fetchone()[0]
        blocked = c.execute("SELECT COUNT(*) FROM failed_releases").fetchone()[0]
    return {"missing": missing, "due_now": due, "not_aired": not_aired, "downloading": downloading,
            "set_aside": set_aside, "blocked_releases": blocked}


# ------------------------------------------------------------------ failed and stalled downloads
def handle_failures(cfg=None) -> dict[str, Any]:
    """Block failed or stalled releases and send their episodes back to search."""
    cfg = cfg or get_settings()
    e = _engine()
    out: dict[str, Any] = {"failed": 0, "stalled": 0, "set_aside": 0, "episodes": []}
    with e.cx() as c:
        stalled = [r["id"] for r in c.execute(
            """SELECT id FROM downloads WHERE lower(COALESCE(status,'')) IN ('queued','downloading')
               AND added_at <= datetime('now', ?)""", (f"-{cfg['stall_hours']} hours",))]
    for download_id in stalled:
        try:
            e.mark_release_failed(download_id, reason=f"Stalled: not finished after {cfg['stall_hours']} hours (Autopilot)", retry=True)
            out["stalled"] += 1
        except Exception as exc:  # noqa: BLE001
            out.setdefault("errors", []).append(f"download {download_id}: {exc}")
    with e.cx() as c:
        rows = c.execute(
            """SELECT d.id, d.episode_id, d.error, d.release_name, sr.guid, sr.title
               FROM downloads d LEFT JOIN search_results sr ON sr.id=d.search_result_id
               WHERE lower(COALESCE(d.status,''))='failed'
                 AND NOT EXISTS (SELECT 1 FROM autopilot_handled_downloads h WHERE h.download_id=d.id)""").fetchall()
        for r in rows:
            title = r["title"] or r["release_name"] or f"download {r['id']}"
            reason = r["error"] or "Download failed"
            c.execute("INSERT OR IGNORE INTO failed_releases(guid,title,reason) VALUES(?,?,?)",
                      (r["guid"] or f"download:{r['id']}", title, reason))
            c.execute("INSERT OR IGNORE INTO autopilot_handled_downloads(download_id) VALUES(?)", (r["id"],))
            out["failed"] += 1
            if not r["episode_id"]:
                continue
            c.execute("""INSERT INTO autopilot_episodes(episode_id,attempts,last_failure,last_failed_at)
                         VALUES(?,1,?,CURRENT_TIMESTAMP)
                         ON CONFLICT(episode_id) DO UPDATE SET attempts=attempts+1,
                           last_failure=excluded.last_failure,last_failed_at=CURRENT_TIMESTAMP""",
                      (r["episode_id"], f"{title}: {reason}"))
            attempts = c.execute("SELECT attempts FROM autopilot_episodes WHERE episode_id=?", (r["episode_id"],)).fetchone()[0]
            has_file = c.execute("SELECT TRIM(COALESCE(location,''))<>'' FROM episodes WHERE id=?", (r["episode_id"],)).fetchone()
            if has_file and has_file[0]:
                continue
            if attempts >= cfg["max_attempts"]:
                c.execute("UPDATE autopilot_episodes SET gave_up_at=CURRENT_TIMESTAMP WHERE episode_id=?", (r["episode_id"],))
                c.execute("UPDATE episodes SET status='Failed' WHERE id=?", (r["episode_id"],))
                out["set_aside"] += 1
            else:
                # Back to Wanted and due at once: the next search skips the blocked release.
                c.execute("UPDATE episodes SET status='Wanted', last_search=NULL WHERE id=?", (r["episode_id"],))
            out["episodes"].append({"episode_id": r["episode_id"], "attempts": attempts, "release": title})
        c.commit()
    if out["failed"] or out["stalled"]:
        e.log("autopilot", f"Autopilot: {out['failed']} failed download(s) blocked, {out['stalled']} stalled, "
                           f"{out['set_aside']} episode(s) set aside after {cfg['max_attempts']} attempts", data=out)
    return out


def retry(episode_ids=None) -> dict[str, int]:
    """Put set-aside episodes back into the search rotation (all when episode_ids is None)."""
    e = _engine()
    with e.cx() as c:
        if episode_ids is None:
            ids = [r[0] for r in c.execute("SELECT episode_id FROM autopilot_episodes WHERE gave_up_at IS NOT NULL")]
        else:
            ids = [int(x) for x in episode_ids]
        for eid in ids:
            c.execute("UPDATE autopilot_episodes SET gave_up_at=NULL, attempts=0 WHERE episode_id=?", (eid,))
            c.execute("UPDATE episodes SET status='Wanted', last_search=NULL WHERE id=? AND TRIM(COALESCE(location,''))=''", (eid,))
        c.commit()
    return {"retried": len(ids)}


def set_aside_list(limit=200) -> list[dict[str, Any]]:
    e = _engine()
    with e._read_cx() as c:
        rows = c.execute("""SELECT a.*, e.season, e.episode, e.name, e.airdate, s.name show_name, e.show_id
                            FROM autopilot_episodes a JOIN episodes e ON e.id=a.episode_id JOIN shows s ON s.id=e.show_id
                            WHERE a.gave_up_at IS NOT NULL ORDER BY a.gave_up_at DESC LIMIT ?""", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------ readiness
def readiness() -> dict[str, Any]:
    """Whether searching and sending can work at all; problems stop the search step before it
    marks any episode as searched."""
    e = _engine()
    import advanced, provider_manager
    problems = []
    try:
        providers = [p for p in e.parse_newznab() if provider_manager.eligible(p, "backlog")]
        providers += [p for p in advanced.provider_defs_raw() if provider_manager.eligible(p, "backlog")]
    except Exception:  # noqa: BLE001
        providers = []
    if not providers:
        problems.append("No indexer is enabled for backlog searches. Add or enable one in Settings > Search Providers.")
    simulation = e.as_bool(e.get_setting("TVManager", "simulation_mode", "0"))
    cfg = e.downloader_config_public()
    nzb = cfg["use_nzbs"] and cfg["nzb_method"] and (cfg["sabnzbd"]["configured"] or cfg["nzbget"]["configured"] or cfg["nzb_method"] == "blackhole")
    torrent = cfg["use_torrents"] and cfg["torrent_method"] and (cfg["torrent"]["configured"] or cfg["torrent_method"] == "blackhole")
    if not simulation and not (nzb or torrent):
        problems.append("No download client is set up. Configure SABnzbd, NZBGet or a torrent client in Settings > Download Clients.")
    return {"ready": not problems, "problems": problems, "providers": len(providers), "simulation": simulation}


# ------------------------------------------------------------------ one run
def run_cycle(progress=None) -> dict[str, Any]:
    e = _engine()
    cfg = get_settings()
    started = time.monotonic()
    deadline = started + cfg["max_minutes"] * 60
    simulation = e.as_bool(e.get_setting("TVManager", "simulation_mode", "0"))
    result: dict[str, Any] = {"ok": True, "simulation": simulation, "steps": {}}

    def step(name, fn):
        try:
            result["steps"][name] = fn()
        except Exception as exc:  # noqa: BLE001 - one failing step must not stop the others
            result["steps"][name] = {"error": str(exc)}
            result.setdefault("errors", []).append(f"{name}: {exc}")

    step("downloads", e.poll_downloaders)
    step("failures", lambda: handle_failures(cfg))
    if cfg["postprocess"]:
        def postprocess():
            out = e.scan_postprocess(dry_run=simulation)
            return {k: out.get(k) for k in ("processed", "matched", "skipped", "errors", "dry_run") if k in out}
        step("postprocess", postprocess)

    searched = grabbed = found = 0
    search_errors: list[str] = []
    ready = readiness()
    if not ready["ready"]:
        # Nothing is searched, so no episode is pushed back by the retry wait.
        result["errors"] = result.get("errors", []) + ready["problems"]
        result["steps"]["search"] = {"due": 0, "searched": 0, "acceptable_results": 0, "sent_to_downloader": 0,
                                     "errors": ready["problems"], "skipped": True}
        result["counts"] = counts(cfg)
        result["seconds"] = round(time.monotonic() - started, 1)
        e.log("autopilot", "Autopilot could not search: " + " ".join(ready["problems"]), "warning", data=result)
        return result
    ids = eligible_episode_ids(cfg)
    for eid in ids:
        if time.monotonic() > deadline:
            result["stopped_early"] = f"Time limit of {cfg['max_minutes']} minutes reached"
            break
        try:
            res = e.search_episode(eid, auto_grab=not simulation, purpose="backlog")
            searched += 1
            found += len([x for x in res.get("results") or [] if not x.get("rejected_reason")])
            if res.get("grabbed"):
                grabbed += 1
            search_errors = list(dict.fromkeys([*search_errors, *(res.get("errors") or [])]))[:20]
        except Exception as exc:  # noqa: BLE001
            search_errors.append(f"episode {eid}: {exc}")
        if progress:
            progress(searched, len(ids))
    result["steps"]["search"] = {"due": len(ids), "searched": searched, "acceptable_results": found,
                                 "sent_to_downloader": grabbed, "errors": search_errors[:20]}
    result["counts"] = counts(cfg)
    result["seconds"] = round(time.monotonic() - started, 1)
    e.log("autopilot", f"Autopilot: searched {searched} missing episode(s), sent {grabbed} to the downloader"
                       f"{' (simulation)' if simulation else ''}; {result['counts']['missing']} still missing, "
                       f"{result['counts']['not_aired']} not aired yet", data=result)
    return result


def summary_for_log(result: dict[str, Any]) -> dict[str, Any]:
    """Compact form of a run for the job history (stored messages are limited to 2,000 characters)."""
    def short(items, n=4):
        return [str(x)[:140] for x in (items or [])[:n]]
    steps = result.get("steps") or {}
    downloads = steps.get("downloads")
    if isinstance(downloads, list):
        downloads = {"clients": len(downloads), "errors": short([d.get("error") for d in downloads if isinstance(d, dict) and d.get("error")])}
    search = dict(steps.get("search") or {})
    search["errors"] = short(search.get("errors"))
    failures = dict(steps.get("failures") or {})
    failures.pop("episodes", None)
    post = steps.get("postprocess")
    if isinstance(post, dict):
        post = {k: (len(v) if isinstance(v, list) else v) for k, v in post.items()}
    return {"simulation": result.get("simulation"), "seconds": result.get("seconds"),
            "stopped_early": result.get("stopped_early"), "errors": short(result.get("errors")),
            "counts": result.get("counts"),
            "steps": {"downloads": downloads, "failures": failures, "postprocess": post, "search": search}}


def status() -> dict[str, Any]:
    e = _engine()
    cfg = get_settings()
    with e._read_cx() as c:
        job = c.execute("SELECT * FROM scheduler_jobs WHERE name=?", (JOB_NAME,)).fetchone()
        runs = c.execute("""SELECT started_at,finished_at,status,message FROM scheduler_runs
                            WHERE job_name=? ORDER BY id DESC LIMIT 10""", (JOB_NAME,)).fetchall()
    history = []
    for r in runs:
        item = {"started_at": r["started_at"], "finished_at": r["finished_at"], "status": r["status"]}
        try:
            msg = json.loads(r["message"] or "{}")
            item["search"] = (msg.get("steps") or {}).get("search")
            item["failures"] = (msg.get("steps") or {}).get("failures")
            item["errors"] = msg.get("errors")
            item["seconds"] = msg.get("seconds")
        except (TypeError, ValueError):
            item["message"] = r["message"]
        history.append(item)
    automation = e.as_bool(e.get_setting("TVManager", "automation_enabled", "0"))
    return {
        "ok": True,
        "settings": {**cfg, "interval_minutes": job["interval_minutes"] if job else DEFAULT_INTERVAL_MINUTES},
        "running": bool(job) and bool(job["enabled"]) and automation and bool(cfg["enabled"]),
        "automation_armed": automation,
        "job": dict(job) if job else None,
        "simulation": e.as_bool(e.get_setting("TVManager", "simulation_mode", "0")),
        "counts": counts(cfg),
        "readiness": readiness(),
        "history": history,
        "set_aside": set_aside_list(50),
        "today": date.today().isoformat(),
    }
