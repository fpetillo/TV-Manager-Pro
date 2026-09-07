from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import dbcore
import threading
import time
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin
import smtplib
from email.message import EmailMessage

import requests
import advanced
import ops
import intelligence
import completion
import production
import release
import sync
import lifecycle
import scheduler_guard
import metadata_service
import integrity
import naming
import database_safety
import library_maintenance
import episode_rules

BASE = Path(__file__).resolve().parent
DB = BASE / "tvmanager.db"
_LOCK = threading.Lock()
_STOP = threading.Event()
_RUNNING = set()

MEDIA_EXTS = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".ts", ".mpeg", ".mpg", ".wmv"}
STATUS_NAMES = {
    1: "Unaired",
    2: "Snatched",
    3: "Wanted",
    4: "Downloaded",
    5: "Skipped",
    6: "Archived",
    7: "Ignored",
    8: "Failed",
    9: "Snatched Proper",
    10: "Subtitled",
}

def cx(readonly=False):
    return dbcore.connect(DB, readonly=readonly)

def now_iso():
    return datetime.now().replace(microsecond=0).isoformat()

def as_bool(v, default=False):
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "on", "enabled"}

def as_int(v, default=0):
    try:
        return int(str(v).strip())
    except Exception:
        return default

def get_setting(section, name, default=None):
    with cx() as c:
        r = c.execute("SELECT value FROM settings WHERE lower(section)=lower(?) AND lower(name)=lower(?)",
                      (section, name)).fetchone()
    return default if not r else r["value"]

def set_setting(section, name, value, is_secret=0, source="tvmanager"):
    with cx() as c:
        c.execute("""INSERT INTO settings(section,name,value,is_secret,source,updated_at)
                     VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
                     ON CONFLICT(section,name) DO UPDATE SET
                       value=excluded.value,is_secret=excluded.is_secret,
                       source=excluded.source,updated_at=CURRENT_TIMESTAMP""",
                  (section, name, "" if value is None else str(value), is_secret, source))
        c.commit()

def public_setting(section, name, default=None):
    v = get_setting(section, name, default)
    return v

def log(event_type, message, level="info", show_id=None, episode_id=None, data=None, conn=None):
    owns = conn is None
    payload=(level, event_type, show_id, episode_id, message,
             json.dumps(data, default=str) if data is not None else None)
    if conn is not None:
        conn.execute("""INSERT INTO activity_log(level,event_type,show_id,episode_id,message,data,created_at)
                        VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)""", payload)
        return

    def write_db():
        with cx() as c:
            c.execute("""INSERT INTO activity_log(level,event_type,show_id,episode_id,message,data,created_at)
                         VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)""", payload)
            c.commit()

    try:
        return dbcore.retry(write_db, attempts=8)
    except Exception as exc:
        # Logging must never take down scheduler or downloader threads. Keep a
        # plain-text emergency trail for support if SQLite is unavailable.
        try:
            emergency=BASE/"logs"/"emergency.log"
            emergency.parent.mkdir(parents=True, exist_ok=True)
            emergency.write_text(
                (emergency.read_text(encoding="utf-8") if emergency.exists() else "") +
                f"{now_iso()} {level.upper()} {event_type}: {message} | log_error={exc}\n",
                encoding="utf-8")
        except Exception:
            pass

def init_engine():
    import show_preferences
    with cx() as c: show_preferences.init(c)
    advanced.init()
    ops.init()
    intelligence.init()
    completion.init()
    production.init()
    release.init()
    sync.init()
    metadata_service.init()
    with cx() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS search_results(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          episode_id INTEGER NOT NULL,
          provider TEXT NOT NULL,
          protocol TEXT NOT NULL DEFAULT 'nzb',
          title TEXT NOT NULL,
          url TEXT,
          guid TEXT,
          size INTEGER,
          publish_date TEXT,
          seeders INTEGER,
          quality TEXT,
          score REAL DEFAULT 0,
          rejected_reason TEXT,
          status TEXT DEFAULT 'Found',
          raw_json TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_search_episode ON search_results(episode_id);
        CREATE INDEX IF NOT EXISTS idx_search_guid ON search_results(guid);

        CREATE TABLE IF NOT EXISTS downloads(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          episode_id INTEGER,
          search_result_id INTEGER,
          client TEXT,
          provider TEXT,
          release_name TEXT,
          external_id TEXT,
          status TEXT DEFAULT 'Queued',
          url TEXT,
          error TEXT,
          added_at TEXT DEFAULT CURRENT_TIMESTAMP,
          completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_download_episode ON downloads(episode_id);

        CREATE TABLE IF NOT EXISTS failed_releases(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          guid TEXT,
          title TEXT,
          reason TEXT,
          failed_at TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(guid)
        );

        CREATE TABLE IF NOT EXISTS activity_log(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          level TEXT DEFAULT 'info',
          event_type TEXT,
          show_id INTEGER,
          episode_id INTEGER,
          message TEXT,
          data TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_activity_date ON activity_log(created_at);

        CREATE TABLE IF NOT EXISTS scheduler_jobs(
          name TEXT PRIMARY KEY,
          enabled INTEGER DEFAULT 0,
          interval_minutes INTEGER NOT NULL,
          last_run TEXT,
          next_run TEXT,
          last_status TEXT,
          last_message TEXT
        );

        CREATE TABLE IF NOT EXISTS postprocess_history(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_path TEXT,
          destination_path TEXT,
          show_id INTEGER,
          episode_id INTEGER,
          method TEXT,
          status TEXT,
          message TEXT,
          processed_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS quality_profiles(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          min_resolution INTEGER DEFAULT 720,
          max_resolution INTEGER DEFAULT 1080,
          preferred_source TEXT DEFAULT 'WEB-DL',
          allow_hevc INTEGER DEFAULT 1,
          upgrade_allowed INTEGER DEFAULT 1,
          cutoff_resolution INTEGER DEFAULT 1080,
          min_size_mb INTEGER DEFAULT 0,
          max_size_mb INTEGER DEFAULT 0,
          preferred_words TEXT,
          required_words TEXT,
          ignored_words TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS notification_history(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          channel TEXT,
          event_type TEXT,
          target TEXT,
          status TEXT,
          message TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scene_exceptions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          show_id INTEGER NOT NULL,
          exception_name TEXT NOT NULL,
          source TEXT DEFAULT 'manual',
          notes TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(show_id, exception_name)
        );
        CREATE INDEX IF NOT EXISTS idx_scene_exceptions_show ON scene_exceptions(show_id);

        CREATE TABLE IF NOT EXISTS mass_update_history(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          action TEXT NOT NULL,
          filter_json TEXT,
          affected INTEGER DEFAULT 0,
          message TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        # Future-facing per-show controls.
        cols = {r["name"] for r in c.execute("PRAGMA table_info(shows)").fetchall()}
        for name, definition in {
            "monitor_new": "INTEGER DEFAULT 1",
            "search_enabled": "INTEGER DEFAULT 1",
            "preferred_words": "TEXT",
            "required_words": "TEXT",
            "ignored_words": "TEXT",
            "season_folders": "INTEGER DEFAULT 1",
            "scene_numbering": "INTEGER DEFAULT 0",
            "air_by_date": "INTEGER DEFAULT 0",
            "sports": "INTEGER DEFAULT 0",
            "metadata_enabled": "INTEGER DEFAULT 1",
            "quality_profile_id": "INTEGER",
        }.items():
            if name not in cols:
                c.execute(f'ALTER TABLE shows ADD COLUMN "{name}" {definition}')

        ecols = {r["name"] for r in c.execute("PRAGMA table_info(episodes)").fetchall()}
        for name, definition in {
            "monitored": "INTEGER DEFAULT 1",
            "last_search": "TEXT",
            "search_count": "INTEGER DEFAULT 0",
            "overview": "TEXT",
            "still_url": "TEXT",
            "still_path": "TEXT",
            "tmdb_episode_id": "INTEGER",
            "metadata_updated_at": "TEXT",
            "ignored": "INTEGER DEFAULT 0",
            "ignored_reason": "TEXT",
            "ignored_at": "TEXT",
            "ignored_source": "TEXT",
            "managed_note": "TEXT",
        }.items():
            if name not in ecols:
                c.execute(f'ALTER TABLE episodes ADD COLUMN "{name}" {definition}')

        daily = max(30, as_int(get_setting("General", "dailysearch_frequency", 120), 120))
        backlog = max(60, as_int(get_setting("General", "backlog_frequency", 2880), 2880))
        meta = max(60, min(360, as_int(get_setting("General", "update_frequency", 168), 168) * 60))
        jobs = [
            ("recent_search", daily),
            ("backlog_search", backlog),
            ("metadata_refresh", meta),
            ("download_status", 5),
            ("subtitle_jobs", 60),
            ("watched_sync", 360),
            ("post_processing", max(10, as_int(get_setting("General", "autopostprocessor_frequency", 10), 10))),
            ("missing_metadata", max(60, as_int(get_setting("TVManager", "missing_metadata_frequency", 720), 720))),
            ("artwork_refresh", max(120, as_int(get_setting("TVManager", "artwork_refresh_frequency", 1440), 1440))),
            ("library_health_scan", max(60, as_int(get_setting("TVManager", "library_health_frequency", 1440), 1440))),
            ("database_protection", max(60, as_int(get_setting("TVManager", "database_protection_frequency", 1440), 1440))),
        ]
        for name, interval in jobs:
            c.execute("""INSERT INTO scheduler_jobs(name,enabled,interval_minutes)
                         VALUES(?,?,?)
                         ON CONFLICT(name) DO UPDATE SET interval_minutes=excluded.interval_minutes""",
                      (name, 0, interval))
        profiles = [
            ("HD 720p",720,720,"WEB-DL",1,1,720),
            ("HD 1080p",720,1080,"WEB-DL",1,1,1080),
            ("Ultra HD",1080,2160,"WEB-DL",1,1,2160),
            ("Archive / Any",0,2160,"",1,0,2160),
        ]
        for p in profiles:
            c.execute("""INSERT OR IGNORE INTO quality_profiles(
                         name,min_resolution,max_resolution,preferred_source,allow_hevc,
                         upgrade_allowed,cutoff_resolution)
                         VALUES(?,?,?,?,?,?,?)""", p)
        c.commit()

    # Migration safety: never auto-arm only because SickChill was armed.
    if get_setting("TVManager", "automation_enabled") is None:
        set_setting("TVManager", "automation_enabled", "0")
    if get_setting("TVManager", "auto_grab") is None:
        set_setting("TVManager", "auto_grab", "1")
    if get_setting("TVManager", "recent_days") is None:
        set_setting("TVManager", "recent_days", "14")
    if get_setting("TVManager", "max_searches_per_run") is None:
        set_setting("TVManager", "max_searches_per_run", "25")
    if get_setting("TVManager", "metadata_missing_limit") is None:
        set_setting("TVManager", "metadata_missing_limit", "200")
    if get_setting("TVManager", "artwork_refresh_limit") is None:
        set_setting("TVManager", "artwork_refresh_limit", "200")
    if get_setting("TVManager", "background_worker_limit") is None:
        set_setting("TVManager", "background_worker_limit", "4")
    if get_setting("TVManager", "ignore_season_zero_counts") is None:
        set_setting("TVManager", "ignore_season_zero_counts", "1")
    if get_setting("TVManager", "specials_hidden_from_wanted_v18_3_1") is None:
        set_setting("TVManager", "ignore_season_zero_counts", "1")
        set_setting("TVManager", "specials_hidden_from_wanted_v18_3_1", "1")
    try:
        episode_rules.init(DB)
    except Exception:
        pass


def list_quality_profiles():
    with cx() as c:
        return [dict(r) for r in c.execute("SELECT * FROM quality_profiles ORDER BY id").fetchall()]

def save_quality_profile(data):
    pid = data.get("id")
    fields = {
        "name": data.get("name") or "Unnamed Profile",
        "min_resolution": as_int(data.get("min_resolution"), 720),
        "max_resolution": as_int(data.get("max_resolution"), 1080),
        "preferred_source": data.get("preferred_source") or "",
        "allow_hevc": 1 if as_bool(data.get("allow_hevc"), True) else 0,
        "upgrade_allowed": 1 if as_bool(data.get("upgrade_allowed"), True) else 0,
        "cutoff_resolution": as_int(data.get("cutoff_resolution"), 1080),
        "min_size_mb": as_int(data.get("min_size_mb"), 0),
        "max_size_mb": as_int(data.get("max_size_mb"), 0),
        "preferred_words": data.get("preferred_words") or "",
        "required_words": data.get("required_words") or "",
        "ignored_words": data.get("ignored_words") or "",
    }
    with cx() as c:
        if pid:
            sets=",".join(f"{k}=?" for k in fields)
            c.execute(f"UPDATE quality_profiles SET {sets} WHERE id=?",
                      list(fields.values())+[int(pid)])
            out=int(pid)
        else:
            cols=",".join(fields)
            qs=",".join("?" for _ in fields)
            cur=c.execute(f"INSERT INTO quality_profiles({cols}) VALUES({qs})", list(fields.values()))
            out=cur.lastrowid
        c.commit()
    return out

def delete_quality_profile(pid):
    with cx() as c:
        used=c.execute("SELECT COUNT(*) c FROM shows WHERE quality_profile_id=?",(pid,)).fetchone()["c"]
        if used:
            raise ValueError(f"Profile is assigned to {used} shows")
        c.execute("DELETE FROM quality_profiles WHERE id=?",(pid,))
        c.commit()

def setting_sections_public():
    with cx() as c:
        rows=c.execute("""SELECT section,COUNT(*) setting_count,
                          SUM(CASE WHEN is_secret=1 THEN 1 ELSE 0 END) secret_count
                          FROM settings GROUP BY section ORDER BY section COLLATE NOCASE""").fetchall()
    return [dict(r) for r in rows]

def settings_for_section(section):
    with cx() as c:
        rows=c.execute("""SELECT section,name,value,is_secret,source,updated_at
                          FROM settings WHERE lower(section)=lower(?) ORDER BY name COLLATE NOCASE""",
                       (section,)).fetchall()
    out=[]
    for r in rows:
        d=dict(r)
        if d["is_secret"] and d["value"]:
            d["value"]="••••••••"
            d["has_value"]=True
        else:
            d["has_value"]=bool(d["value"])
        out.append(d)
    return out

def update_setting_safe(section,name,value):
    with cx() as c:
        old=c.execute("""SELECT is_secret,value FROM settings
                         WHERE lower(section)=lower(?) AND lower(name)=lower(?)""",
                      (section,name)).fetchone()
    secret = int(old["is_secret"]) if old else (1 if is_secret_like(name) else 0)
    if secret and value == "••••••••":
        return
    set_setting(section,name,value,secret,"tvmanager")

def is_secret_like(name):
    n=str(name).lower()
    return any(x in n for x in ("password","passwd","apikey","api_key","token","secret","cookie","username","user_key","passkey"))

def dashboard_stats():
    with cx() as c:
        stats={}
        stats["shows"]=c.execute("SELECT COUNT(*) c FROM shows").fetchone()["c"]
        stats["episodes"]=c.execute("SELECT COUNT(*) c FROM episodes").fetchone()["c"]
        stats["wanted"]=c.execute("SELECT COUNT(*) c FROM episodes WHERE lower(COALESCE(status,'')) IN ('wanted','failed')").fetchone()["c"]
        stats["snatched"]=c.execute("SELECT COUNT(*) c FROM episodes WHERE lower(COALESCE(status,''))='snatched'").fetchone()["c"]
        stats["downloaded"]=c.execute("SELECT COUNT(*) c FROM episodes WHERE lower(COALESCE(status,''))='downloaded'").fetchone()["c"]
        stats["unaired"]=c.execute("SELECT COUNT(*) c FROM episodes WHERE lower(COALESCE(status,''))='unaired'").fetchone()["c"]
        stats["providers"]=len([p for p in parse_newznab() if p["enabled"]])
        stats["downloads"]=c.execute("SELECT COUNT(*) c FROM downloads").fetchone()["c"]
        stats["failed"]=c.execute("SELECT COUNT(*) c FROM failed_releases").fetchone()["c"]
    return stats

def mark_release_failed(download_id, reason="Marked failed by user", retry=True):
    with cx() as c:
        d=c.execute("""SELECT d.*,sr.guid,sr.title sr_title,e.show_id
                       FROM downloads d
                       LEFT JOIN search_results sr ON sr.id=d.search_result_id
                       LEFT JOIN episodes e ON e.id=d.episode_id
                       WHERE d.id=?""",(download_id,)).fetchone()
        if not d:
            raise ValueError("Download not found")
        guid=d["guid"] or f"download:{download_id}"
        title=d["sr_title"] or d["release_name"]
        c.execute("""INSERT OR IGNORE INTO failed_releases(guid,title,reason) VALUES(?,?,?)""",
                  (guid,title,reason))
        lifecycle.transition("episode",download_id,d["status"],"Failed",message=reason,conn=c,force=True)
        c.execute("UPDATE downloads SET error=? WHERE id=?",(reason,download_id))
        if d["episode_id"]:
            c.execute("UPDATE episodes SET status=? WHERE id=?",("Wanted" if retry else "Failed",d["episode_id"]))
        c.commit()
    log("download_failed", f"{title}: {reason}", "warning",
        show_id=d["show_id"],episode_id=d["episode_id"])
    try:advanced.fire_webhooks("failed",{"release":title})
    except Exception:pass
    return {"ok":True,"episode_status":"Wanted" if retry else "Failed"}

def notification_channels():
    sections = [
        "Email","Slack","Discord","Telegram","Plex","KODI","Emby","Pushover","Pushbullet",
        "Growl","Join","NMA","Prowl","Pushalot","Twitter","Twilio","Boxcar2","Gotify",
        "Mattermost","MattermostBot","RocketChat","SynologyNotifier"
    ]
    out=[]
    for sec in sections:
        vals=settings_for_section(sec)
        if vals:
            enabled=False
            for item in vals:
                if item["name"].lower().endswith("notify") or item["name"].lower() in {"use_email","enabled","use_slack","use_discord","use_telegram"}:
                    if as_bool(item["value"],False):
                        enabled=True
            out.append({"section":sec,"enabled":enabled,"settings":len(vals)})
    return out

def send_test_email():
    host=get_setting("Email","email_host","") or get_setting("Email","host","")
    port=as_int(get_setting("Email","email_port","25"),25)
    user=get_setting("Email","email_user","") or get_setting("Email","username","")
    password=get_setting("Email","email_password","") or get_setting("Email","password","")
    tls=as_bool(get_setting("Email","email_tls","0"))
    sender=get_setting("Email","email_from","") or user
    to=get_setting("Email","email_list","") or get_setting("Email","email_to","")
    if not host or not to:
        raise ValueError("Email host and recipient are not configured")
    recipients=[x.strip() for x in re.split(r"[,;]",to) if x.strip()]
    msg=EmailMessage()
    msg["Subject"]="TV Manager notification test"
    msg["From"]=sender or "tvmanager@localhost"
    msg["To"]=", ".join(recipients)
    msg.set_content("TV Manager successfully connected to your configured email notification service.")
    with smtplib.SMTP(host,port,timeout=15) as s:
        if tls: s.starttls()
        if user: s.login(user,password or "")
        s.send_message(msg)
    with cx() as c:
        c.execute("""INSERT INTO notification_history(channel,event_type,target,status,message)
                     VALUES('Email','test',?,'OK','Test email sent')""",(to,))
        c.commit()
    return {"ok":True,"channel":"Email","target":to}

def status_label(raw):
    if raw is None or str(raw).strip() == "":
        return "Unknown"
    t = str(raw).strip()
    if not re.fullmatch(r"-?\d+", t):
        return t.title()
    n = int(t)
    # SickChill composite statuses encode quality in the hundreds and base status in the remainder.
    base = n % 100
    return STATUS_NAMES.get(base, f"Legacy {n}")

def normalize_statuses():
    # Preserve legacy_data/raw context while making operational statuses usable.
    with cx() as c:
        rows = c.execute("SELECT id,status,location FROM episodes").fetchall()
        for r in rows:
            label = status_label(r["status"])
            if r["location"] and label in {"Unknown", "Wanted", "Skipped", "Unaired"}:
                label = "Downloaded"
            c.execute("UPDATE episodes SET status=? WHERE id=?", (label, r["id"]))
        c.commit()

def parse_words(v):
    if not v:
        return []
    t = str(v).strip().strip('"').strip("'")
    parts = re.split(r"[,|]", t)
    return [x.strip().lower() for x in parts if x.strip()]

def infer_quality(title):
    t = title.lower()
    res = "2160p" if "2160p" in t or "4k" in t else "1080p" if "1080p" in t else "720p" if "720p" in t else "SD"
    src = "BluRay" if "bluray" in t or "blu-ray" in t else "WEB-DL" if "web-dl" in t or "webdl" in t else "WEBRip" if "webrip" in t else "HDTV" if "hdtv" in t else ""
    codec = "x265/HEVC" if any(x in t for x in ("x265", "h265", "hevc")) else "x264/AVC" if any(x in t for x in ("x264", "h264", "avc")) else ""
    return " ".join(x for x in (res, src, codec) if x)

def score_release(title, show=None):
    t = title.lower()
    profile=None
    if show and show.get("quality_profile_id"):
        with cx() as c:
            r=c.execute("SELECT * FROM quality_profiles WHERE id=?",(show.get("quality_profile_id"),)).fetchone()
            profile=dict(r) if r else None
    ignored = parse_words(get_setting("General", "ignore_words", "")) + parse_words((show or {}).get("ignored_words") if show else "")
    required = parse_words(get_setting("General", "require_words", "")) + parse_words((show or {}).get("required_words") if show else "")
    preferred = parse_words(get_setting("General", "prefer_words", "")) + parse_words((show or {}).get("preferred_words") if show else "")
    if profile:
        ignored += parse_words(profile.get("ignored_words"))
        required += parse_words(profile.get("required_words"))
        preferred += parse_words(profile.get("preferred_words"))
    for w in ignored:
        if w and w in t:
            return -10000, f"Ignored word: {w}"
    for w in required:
        if w and w not in t:
            return -10000, f"Required word missing: {w}"
    if profile:
        detected = 2160 if ("2160p" in t or "4k" in t) else 1080 if "1080p" in t else 720 if "720p" in t else 480
        if detected < int(profile.get("min_resolution") or 0):
            return -10000, f"Below profile minimum {profile.get('min_resolution')}p"
        if detected > int(profile.get("max_resolution") or 2160):
            return -10000, f"Above profile maximum {profile.get('max_resolution')}p"
        if not profile.get("allow_hevc") and any(x in t for x in ("x265","h265","hevc")):
            return -10000, "HEVC is disabled by quality profile"
    score = 0
    if "2160p" in t or "4k" in t: score += 45
    elif "1080p" in t: score += 35
    elif "720p" in t: score += 25
    else: score += 10
    if "web-dl" in t or "webdl" in t: score += 10
    elif "bluray" in t or "blu-ray" in t: score += 9
    elif "webrip" in t: score += 7
    elif "hdtv" in t: score += 5
    if "repack" in t: score += 8
    elif "proper" in t: score += 6
    if any(x in t for x in ("x265", "h265", "hevc")): score += 3
    for idx, w in enumerate(preferred):
        if w and w in t:
            score += max(1, 10 - idx)
    return score, None

def parse_newznab():
    raw = get_setting("Newznab", "newznab_data", "") or ""
    raw = raw.strip().strip('"')
    order = (get_setting("General", "provider_order", "") or "").split()
    order_map = {name.lower(): idx for idx, name in enumerate(order)}
    providers = []
    for chunk in raw.split("!!!"):
        parts = chunk.split("|")
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        url = parts[1].strip()
        key = parts[2].strip() if len(parts) > 2 else ""
        cats = parts[3].strip() if len(parts) > 3 else ""
        enabled_field = parts[4].strip() if len(parts) > 4 else "1"
        # SickChill config variants have changed over time; provider_order is the strongest signal.
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        enabled = slug in order_map or name.lower().replace(".", "_") in order_map or enabled_field in {"1", "true", "True"}
        providers.append({
            "name": name,
            "url": url,
            "api_key": key,
            "categories": cats,
            "enabled": enabled,
            "priority": order_map.get(slug, order_map.get(name.lower().replace(".", "_"), 9999)),
            "protocol": "nzb",
        })
    providers.sort(key=lambda x: (not x["enabled"], x["priority"], x["name"].lower()))
    return providers

def provider_public():
    out = []
    for p in parse_newznab():
        out.append({
            "name": p["name"], "url": p["url"], "categories": p["categories"],
            "enabled": p["enabled"], "priority": p["priority"], "protocol": p["protocol"],
            "has_api_key": bool(p["api_key"]),
        })
    return out

def _xml_text(el, tag):
    node = el.find(tag)
    return node.text.strip() if node is not None and node.text else None

def search_newznab(provider, show, episode, timeout=25):
    base = provider["url"].rstrip("/") + "/api"
    params = {
        "t": "tvsearch",
        "q": show["name"],
        "season": episode["season"],
        "ep": episode["episode"],
        "extended": "1",
        "o": "xml",
    }
    params.update(__import__("show_preferences").search_parameters(show,episode))
    if params["t"]=="search":
        params.pop("season",None);params.pop("ep",None)
    if provider["api_key"]:
        params["apikey"] = provider["api_key"]
    if provider["categories"]:
        params["cat"] = provider["categories"]
    r = requests.get(base, params=params, timeout=timeout,
                     headers={"User-Agent": "TVManager/4.0"})
    r.raise_for_status()
    root = ET.fromstring(r.content)
    found = []
    for item in root.findall(".//item"):
        title = _xml_text(item, "title") or ""
        link = _xml_text(item, "link") or ""
        guid = _xml_text(item, "guid") or link or title
        pub = _xml_text(item, "pubDate")
        enclosure = item.find("enclosure")
        size = 0
        if enclosure is not None:
            link = enclosure.attrib.get("url") or link
            try: size = int(enclosure.attrib.get("length") or 0)
            except Exception: size = 0
        attrs = {}
        for node in item.iter():
            if node.tag.endswith("attr"):
                n = node.attrib.get("name")
                if n: attrs[n] = node.attrib.get("value")
        try: seeders = int(attrs.get("seeders") or 0)
        except Exception: seeders = 0
        score, rejected = score_release(title, dict(show))
        found.append({
            "provider": provider["name"], "protocol": "nzb", "title": title,
            "url": link, "guid": guid, "size": size, "publish_date": pub,
            "seeders": seeders, "quality": infer_quality(title), "score": score,
            "rejected_reason": rejected,
        })
    return found


def search_generic_provider(provider, show, episode, timeout=25):
    base=provider["url"].rstrip("/")+"/api"
    params={"t":"tvsearch","q":show["name"],"season":episode["season"],"ep":episode["episode"],"extended":"1","o":"xml"}
    params.update(__import__("show_preferences").search_parameters(show,episode))
    if params["t"]=="search":
        params.pop("season",None);params.pop("ep",None)
    if provider.get("api_key"):params["apikey"]=provider["api_key"]
    if provider.get("categories"):params["cat"]=provider["categories"]
    r=requests.get(base,params=params,timeout=timeout,headers={"User-Agent":"TVManager/6.1"})
    r.raise_for_status()
    root=ET.fromstring(r.content)
    out=[]
    for item in root.findall(".//item"):
        title=_xml_text(item,"title") or "";link=_xml_text(item,"link") or "";guid=_xml_text(item,"guid") or link or title
        enclosure=item.find("enclosure");size=0
        if enclosure is not None:
            link=enclosure.attrib.get("url") or link
            try:size=int(enclosure.attrib.get("length") or 0)
            except Exception:size=0
        attrs={}
        for node in item.iter():
            if node.tag.endswith("attr") and node.attrib.get("name"):
                attrs[node.attrib["name"]]=node.attrib.get("value")
        try:seeders=int(attrs.get("seeders") or 0)
        except Exception:seeders=0
        if provider.get("protocol")=="torznab" and seeders<int(provider.get("minimum_seeders") or 0):
            score,rejected=-10000,f"Below minimum seeders ({provider.get('minimum_seeders')})"
        else:
            score,rejected=score_release(title,dict(show))
        out.append({"provider":provider["name"],"protocol":"torrent" if provider.get("protocol")=="torznab" else "nzb",
                    "title":title,"url":link,"guid":guid,"size":size,"publish_date":_xml_text(item,"pubDate"),
                    "seeders":seeders,"quality":infer_quality(title),"score":score-(int(provider.get("priority") or 100)/1000),
                    "rejected_reason":rejected})
    return out



def ignore_specials_from_wanted() -> bool:
    """Global product policy: S00/Specials are hidden from Missing/Wanted workflows unless explicitly re-enabled."""
    return as_bool(get_setting("TVManager", "ignore_season_zero_counts", "1"), True)

def specials_wanted_sql(alias="e") -> str:
    return f" AND COALESCE({alias}.season,-1)<>0" if ignore_specials_from_wanted() else ""

def _episode_context(episode_id):
    with cx() as c:
        row = c.execute("""SELECT e.*,s.name show_name,s.paused,s.search_enabled,
                                 s.preferred_words,s.required_words,s.ignored_words,
                                 s.quality show_quality,s.quality_profile_id,s.id show_id,s.scene_numbering,s.air_by_date,s.sports,s.anime
                          FROM episodes e JOIN shows s ON s.id=e.show_id
                          WHERE e.id=?""", (episode_id,)).fetchone()
    return dict(row) if row else None

def search_episode(episode_id, auto_grab=False):
    ctx = _episode_context(episode_id)
    if not ctx:
        raise ValueError("Episode not found")
    if ctx["paused"] or not ctx["search_enabled"] or not ctx["monitored"] or ctx.get("ignored") or str(ctx.get("status") or "").lower()=="ignored":
        return {"episode_id": episode_id, "results": [], "message": "Show or episode is paused/unmonitored or ignored."}
    if ignore_specials_from_wanted() and int(ctx["season"] or 0) == 0:
        return {"episode_id": episode_id, "results": [], "message": "Season 00 / Specials are globally hidden from Missing/Wanted and search processing."}
    show = {
        "id": ctx["show_id"], "name": ctx["show_name"],
        "preferred_words": ctx["preferred_words"], "required_words": ctx["required_words"],
        "ignored_words": ctx["ignored_words"], "quality": ctx["show_quality"], "quality_profile_id": ctx["quality_profile_id"],
    }
    names=advanced.aliases(ctx["show_id"])
    if names: show["search_name"]=names[0]
    episode = dict(ctx)
    if ctx.get("scene_numbering"):
        import scene_sync
        episode=scene_sync.for_search(ctx["show_id"],episode)
    show.update({key:ctx.get(key) for key in ("scene_numbering","air_by_date","sports","anime")})
    providers = [p for p in parse_newznab() if p["enabled"]]
    custom = advanced.provider_defs_raw()
    if as_bool(get_setting("General", "randomize_providers", "0")):
        import random
        random.shuffle(providers);random.shuffle(custom)
    all_results = []
    errors = []
    for p in providers:
        if not ops.provider_is_available(p["name"]):
            errors.append(f'{p["name"]}: temporarily suspended after repeated failures')
            continue
        started=time.perf_counter()
        try:
            all_results.extend(search_newznab(p, show, episode))
            ops.provider_result(p["name"],True,(time.perf_counter()-started)*1000)
        except Exception as e:
            ops.provider_result(p["name"],False,(time.perf_counter()-started)*1000,e)
            errors.append(f'{p["name"]}: {e}')
            log("provider_error", f'{p["name"]} search failed: {e}', "warning",
                show_id=show["id"], episode_id=episode_id)
    for p in custom:
        if not ops.provider_is_available(p["name"]):
            errors.append(f'{p["name"]}: temporarily suspended after repeated failures')
            continue
        started=time.perf_counter()
        try:
            all_results.extend(search_generic_provider(p,show,episode))
            ops.provider_result(p["name"],True,(time.perf_counter()-started)*1000)
        except Exception as e:
            ops.provider_result(p["name"],False,(time.perf_counter()-started)*1000,e)
            errors.append(f'{p["name"]}: {e}')
            log("provider_error",f'{p["name"]} search failed: {e}',"warning",
                show_id=show["id"],episode_id=episode_id)
    all_results=[ops.apply_rules(x) for x in all_results]
    deduped=[];seen=set()
    for x in all_results:
        key=(x.get("guid") or x.get("title") or "").lower()
        if key in seen:continue
        seen.add(key);deduped.append(x)
    all_results=deduped
    all_results.sort(key=lambda x: (x["rejected_reason"] is not None, -x["score"], -(x["size"] or 0)))
    with cx() as c:
        c.execute("DELETE FROM search_results WHERE episode_id=? AND status='Found'", (episode_id,))
        ids = []
        for item in all_results:
            cur = c.execute("""INSERT INTO search_results(
                episode_id,provider,protocol,title,url,guid,size,publish_date,seeders,quality,score,
                rejected_reason,status,raw_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (episode_id,item["provider"],item["protocol"],item["title"],item["url"],item["guid"],
                 item["size"],item["publish_date"],item["seeders"],item["quality"],item["score"],
                 item["rejected_reason"],"Rejected" if item["rejected_reason"] else "Found",
                 json.dumps(item, default=str)))
            item["id"] = cur.lastrowid
            ids.append(cur.lastrowid)
            ops.record_decision(episode_id,cur.lastrowid,item,conn=c)
        c.execute("UPDATE episodes SET last_search=CURRENT_TIMESTAMP,search_count=COALESCE(search_count,0)+1 WHERE id=?",
                  (episode_id,))
        c.commit()
    log("episode_search", f'Searched {show["name"]} S{ctx["season"]:02d}E{ctx["episode"]:02d}: {len(all_results)} results',
        show_id=show["id"], episode_id=episode_id, data={"errors": errors})
    grabbed = None
    if auto_grab:
        best = next((x for x in all_results if not x["rejected_reason"]), None)
        if best:
            grabbed = grab_result(best["id"])
    return {"episode_id": episode_id, "results": all_results, "errors": errors, "grabbed": grabbed}

def downloader_config_public():
    nzb_method = (get_setting("General", "nzb_method", "") or "").lower()
    torrent_method = (get_setting("General", "torrent_method", "") or "").lower()
    return {
        "use_nzbs": as_bool(get_setting("General", "use_nzbs", "0")),
        "use_torrents": as_bool(get_setting("General", "use_torrents", "0")),
        "nzb_method": nzb_method,
        "torrent_method": torrent_method,
        "sabnzbd": {
            "configured": bool(get_setting("SABnzbd", "sab_host", "")),
            "host": get_setting("SABnzbd", "sab_host", ""),
            "category": get_setting("SABnzbd", "sab_category", "tv"),
            "has_api_key": bool(get_setting("SABnzbd", "sab_apikey", "")),
        },
        "nzbget": {
            "configured": bool(get_setting("NZBGet","nzbget_host","")),
            "host": get_setting("NZBGet","nzbget_host",""),
            "category": get_setting("NZBGet","nzbget_category","tv"),
        },
        "torrent": {
            "configured": bool(get_setting("TORRENT", "torrent_host", "")),
            "host": get_setting("TORRENT", "torrent_host", ""),
            "label": get_setting("TORRENT", "torrent_label", ""),
        },
    }

def test_sab():
    host = (get_setting("SABnzbd", "sab_host", "") or "").rstrip("/") + "/"
    key = get_setting("SABnzbd", "sab_apikey", "")
    if not host.strip("/"):
        raise ValueError("SABnzbd host is not configured")
    r = requests.get(urljoin(host, "api"), params={"mode":"version","output":"json","apikey":key}, timeout=10)
    r.raise_for_status()
    try: data = r.json()
    except Exception: data = {"response": r.text[:200]}
    return {"ok": True, "client": "SABnzbd", "version": data.get("version") or data.get("response")}

def _qbit_session():
    host = (get_setting("TORRENT", "torrent_host", "") or "").rstrip("/")
    if not host:
        raise ValueError("Torrent host is not configured")
    sess = requests.Session()
    user = get_setting("TORRENT", "torrent_username", "") or ""
    password = get_setting("TORRENT", "torrent_password", "") or ""
    if user or password:
        r = sess.post(host + "/api/v2/auth/login", data={"username":user,"password":password}, timeout=10)
        if r.status_code >= 400 or "Fails" in r.text:
            raise ValueError("qBittorrent authentication failed")
    return sess, host

def test_qbit():
    sess, host = _qbit_session()
    r = sess.get(host + "/api/v2/app/version", timeout=10)
    r.raise_for_status()
    return {"ok": True, "client": "qBittorrent", "version": r.text.strip()}


def test_nzbget():
    host=(get_setting("NZBGet","nzbget_host","") or "").rstrip("/")
    if not host: raise ValueError("NZBGet host is not configured")
    user=get_setting("NZBGet","nzbget_username","") or ""
    password=get_setting("NZBGet","nzbget_password","") or ""
    r=requests.post(host+"/jsonrpc",json={"method":"version","params":[],"id":1},auth=(user,password) if user else None,timeout=10)
    r.raise_for_status();data=r.json()
    return {"ok":True,"client":"NZBGet","version":data.get("result")}

def test_transmission():
    host=(get_setting("TORRENT","torrent_host","") or "").rstrip("/")
    user=get_setting("TORRENT","torrent_username","") or ""
    password=get_setting("TORRENT","torrent_password","") or ""
    url=host+"/transmission/rpc"
    auth=(user,password) if user else None
    r=requests.post(url,json={"method":"session-get"},auth=auth,timeout=10)
    if r.status_code==409:
        sid=r.headers.get("X-Transmission-Session-Id")
        r=requests.post(url,json={"method":"session-get"},headers={"X-Transmission-Session-Id":sid},auth=auth,timeout=10)
    r.raise_for_status();data=r.json()
    return {"ok":True,"client":"Transmission","version":(data.get("arguments") or {}).get("version")}

def test_deluge():
    host=(get_setting("TORRENT","torrent_host","") or "").rstrip("/")
    password=get_setting("TORRENT","torrent_password","") or ""
    sess=requests.Session()
    r=sess.post(host+"/json",json={"method":"auth.login","params":[password],"id":1},timeout=10);r.raise_for_status()
    if not r.json().get("result"):raise ValueError("Deluge authentication failed")
    r=sess.post(host+"/json",json={"method":"web.connected","params":[],"id":2},timeout=10);r.raise_for_status()
    return {"ok":True,"client":"Deluge","connected":bool(r.json().get("result"))}

def send_nzbget(result):
    from downloader_polling import nzb_rpc
    category=get_setting("NZBGet","nzbget_category","tv") or "tv"
    external=nzb_rpc(get_setting,"append",[result["title"]+".nzb",result["url"],category,0,False,False,"",0,"SCORE"])
    if type(external) is not int or external<=0:raise ValueError("NZBGet did not accept the download")
    return str(external)


def send_transmission(result):
    from downloader_polling import transmission_rpc
    args=transmission_rpc(get_setting,"torrent-add",{"filename":result["url"]})
    torrent=args.get("torrent-added") or args.get("torrent-duplicate") or {}
    external=torrent.get("hashString")
    if not external:raise ValueError("Transmission did not return a torrent ID")
    return str(external)


def send_deluge(result):
    host=(get_setting("TORRENT","torrent_host","") or "").rstrip("/")
    password=get_setting("TORRENT","torrent_password","") or ""
    sess=requests.Session()
    r=sess.post(host+"/json",json={"method":"auth.login","params":[password],"id":1},timeout=10);r.raise_for_status()
    if not r.json().get("result"):raise ValueError("Deluge authentication failed")
    opts={}
    label=get_setting("TORRENT","torrent_label","") or ""
    r=sess.post(host+"/json",json={"method":"core.add_torrent_url","params":[result["url"],opts],"id":2},timeout=15);r.raise_for_status()
    data=r.json()
    if data.get("error"):raise ValueError(str(data["error"]))
    return str(data.get("result") or "")

def test_downloaders():
    cfg = downloader_config_public()
    out = []
    if cfg["use_nzbs"] and cfg["nzb_method"] == "sabnzbd":
        try: out.append(test_sab())
        except Exception as e: out.append({"ok":False,"client":"SABnzbd","error":str(e)})
    if cfg["use_nzbs"] and cfg["nzb_method"] == "nzbget":
        try: out.append(test_nzbget())
        except Exception as e: out.append({"ok":False,"client":"NZBGet","error":str(e)})
    if cfg["use_torrents"] and cfg["torrent_method"] == "qbittorrent":
        try: out.append(test_qbit())
        except Exception as e: out.append({"ok":False,"client":"qBittorrent","error":str(e)})
    if cfg["use_torrents"] and cfg["torrent_method"] == "transmission":
        try: out.append(test_transmission())
        except Exception as e: out.append({"ok":False,"client":"Transmission","error":str(e)})
    if cfg["use_torrents"] and cfg["torrent_method"] == "deluge":
        try: out.append(test_deluge())
        except Exception as e: out.append({"ok":False,"client":"Deluge","error":str(e)})
    return out

def send_sab(result):
    host = (get_setting("SABnzbd", "sab_host", "") or "").rstrip("/") + "/"
    params = {
        "mode": "addurl",
        "name": result["url"],
        "apikey": get_setting("SABnzbd", "sab_apikey", ""),
        "cat": get_setting("SABnzbd", "sab_category", "tv"),
        "output": "json",
    }
    if as_bool(get_setting("SABnzbd", "sab_forced", "0")):
        params["priority"] = 2
    r = requests.get(urljoin(host, "api"), params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data.get("status", False):
        raise ValueError(data.get("error") or "SABnzbd rejected the NZB")
    ids = data.get("nzo_ids") or []
    return ids[0] if ids else None

def _magnet_hash(url):
    from urllib.parse import urlparse, parse_qs
    import base64
    if urlparse(str(url)).scheme.lower() != "magnet": return None
    for value in parse_qs(urlparse(url).query).get("xt",[]):
        if not value.lower().startswith("urn:btih:"): continue
        raw=value[9:]
        if re.fullmatch(r"[0-9a-fA-F]{40}",raw): return raw.lower()
        if re.fullmatch(r"[A-Z2-7a-z]{32}",raw): return base64.b32decode(raw.upper()).hex()
    return None


def send_qbit(result):
    sess, host = _qbit_session()
    data = {"urls": result["url"]}
    label = get_setting("TORRENT", "torrent_label", "") or ""
    if label: data["category"] = label
    if as_bool(get_setting("TORRENT", "torrent_paused", "0")):
        data["paused"] = "true"
    r = sess.post(host + "/api/v2/torrents/add", data=data, timeout=15)
    r.raise_for_status()
    if r.text.strip().lower() not in {"ok.", ""}:
        raise ValueError("qBittorrent rejected the torrent: " + r.text[:200])
    return _magnet_hash(result["url"])

def send_blackhole(result):
    if result["protocol"] == "nzb":
        target = get_setting("Blackhole", "nzb_dir", "")
    else:
        target = get_setting("Blackhole", "torrent_dir", "")
    if not target:
        raise ValueError("Blackhole directory is not configured")
    Path(target).mkdir(parents=True, exist_ok=True)
    # For URL-based search results, save a URL descriptor; compatible clients can watch this via helper tooling.
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", result["title"])[:180]
    path = Path(target) / (safe + ".url")
    path.write_text("[InternetShortcut]\nURL=" + (result["url"] or "") + "\n", encoding="utf-8")
    return str(path)

def grab_result(result_id):
    with cx() as c:
        r = c.execute("""SELECT sr.*,e.show_id,e.season,e.episode,e.status episode_status,s.name show_name
                         FROM search_results sr
                         JOIN episodes e ON e.id=sr.episode_id
                         JOIN shows s ON s.id=e.show_id
                         WHERE sr.id=?""", (result_id,)).fetchone()
    if not r:
        raise ValueError("Search result not found")
    if r["rejected_reason"]:
        raise ValueError("This result was rejected: " + r["rejected_reason"])
    with cx() as c:
        bad = c.execute("SELECT 1 FROM failed_releases WHERE guid=? LIMIT 1", (r["guid"],)).fetchone()
    if bad:
        raise ValueError("This release is on the failed-release blacklist")
    cfg = downloader_config_public()
    client = None
    external = None
    try:
        if r["protocol"] == "nzb":
            method = cfg["nzb_method"]
            if method == "sabnzbd":
                client = "SABnzbd"; external = send_sab(r)
            elif method == "nzbget":
                client = "NZBGet"; external = send_nzbget(r)
            elif method == "blackhole":
                client = "Blackhole"; external = send_blackhole(r)
            else:
                raise ValueError(f"NZB method '{method}' is not yet configured for direct sending")
        else:
            method = cfg["torrent_method"]
            if method == "qbittorrent":
                client = "qBittorrent"; external = send_qbit(r)
            elif method == "transmission":
                client = "Transmission"; external = send_transmission(r)
            elif method == "deluge":
                client = "Deluge"; external = send_deluge(r)
            elif method == "blackhole":
                client = "Blackhole"; external = send_blackhole(r)
            else:
                raise ValueError(f"Torrent method '{method}' is not yet configured for direct sending")
        with cx() as c:
            cur = c.execute("""INSERT INTO downloads(episode_id,search_result_id,client,provider,release_name,
                                                     external_id,status,url)
                               VALUES(?,?,?,?,?,?,?,?)""",
                            (r["episode_id"], result_id, client, r["provider"], r["title"],
                             external, "Queued", r["url"]))
            lifecycle.transition("episode",cur.lastrowid,"Found","Queued",
                                 message=f'Queued in {client}',details={"result_id":result_id},conn=c)
            c.execute("UPDATE search_results SET status='Grabbed' WHERE id=?", (result_id,))
            c.execute("UPDATE episodes SET status='Snatched',release_name=? WHERE id=?",
                      (r["title"], r["episode_id"]))
            c.commit()
        payload={"show":r["show_name"],"season":r["season"],"episode":r["episode"],"release":r["title"],"client":client}
        log("download_queued", f'Queued {r["show_name"]} S{r["season"]:02d}E{r["episode"]:02d} in {client}',
            show_id=r["show_id"], episode_id=r["episode_id"],
            data=payload)
        try: advanced.fire_webhooks("snatched",payload)
        except Exception: pass
        return {"ok":True,"client":client,"external_id":external,"download_id":cur.lastrowid}
    except Exception as e:
        log("download_error", f'Failed to queue {r["title"]}: {e}', "error",
            show_id=r["show_id"], episode_id=r["episode_id"])
        raise

def eligible_episodes(kind="recent", limit=25):
    today = date.today()
    params = []
    where = ["""lower(COALESCE(e.status,'')) IN ('wanted','failed','unaired')""",
             "COALESCE(e.monitored,1)=1", "COALESCE(e.ignored,0)=0", "lower(COALESCE(e.status,''))<>'ignored'", "COALESCE(s.paused,0)=0", "COALESCE(s.search_enabled,1)=1"]
    if ignore_specials_from_wanted():
        where.append("COALESCE(e.season,-1)<>0")
    if kind == "recent":
        days = max(1, as_int(get_setting("TVManager", "recent_days", "14"), 14))
        start = (today - timedelta(days=days)).isoformat()
        end = today.isoformat()
        where += ["e.airdate IS NOT NULL", "e.airdate>=?", "e.airdate<=?"]
        params += [start, end]
    else:
        where += ["(e.airdate IS NULL OR e.airdate<=?)"]
        params += [today.isoformat()]
    sql = f"""SELECT e.id FROM episodes e JOIN shows s ON s.id=e.show_id
              WHERE {' AND '.join(where)}
              ORDER BY COALESCE(e.airdate,'1900-01-01') {'DESC' if kind=='recent' else 'ASC'}
              LIMIT ?"""
    params.append(limit)
    with cx() as c:
        return [r["id"] for r in c.execute(sql, params).fetchall()]

def run_search_job(kind="recent", auto_grab=None):
    limit = max(1, as_int(get_setting("TVManager", "max_searches_per_run", "25"), 25))
    ids = eligible_episodes(kind, limit)
    if auto_grab is None:
        auto_grab = as_bool(get_setting("TVManager", "auto_grab", "1"))
    if as_bool(get_setting("TVManager","simulation_mode","0")):
        auto_grab=False
    stats = {"searched":0,"found":0,"grabbed":0,"errors":[]}
    for eid in ids:
        try:
            res = search_episode(eid, auto_grab=auto_grab)
            stats["searched"] += 1
            stats["found"] += len([x for x in res["results"] if not x.get("rejected_reason")])
            if res.get("grabbed"): stats["grabbed"] += 1
        except Exception as e:
            stats["errors"].append(str(e))
    log(f"{kind}_search", f'{kind.title()} search: {stats["searched"]} episodes, {stats["found"]} acceptable results, {stats["grabbed"]} queued',
        data=stats)
    return stats


SUB_EXTS={".srt",".ass",".ssa",".sub",".vtt"}

def _is_probably_remote_media_path(path_text):
    """Return True for UNC/mapped network paths that can freeze on stat()."""
    raw=str(path_text or "").strip()
    if raw.startswith('\\') or raw.startswith('//'):
        return True
    if os.name == 'nt' and len(raw) >= 2 and raw[1] == ':':
        try:
            import ctypes
            root=raw[:3] if len(raw) >= 3 and raw[2] in ('\\','/') else raw[:2]+'\\'
            dtype=ctypes.windll.kernel32.GetDriveTypeW(root)
            return int(dtype) == 4  # DRIVE_REMOTE
        except Exception:
            return False
    return False
def subtitle_scan(show_id=None, progress_callback=None, max_seconds=None, batch_size=50, max_candidates=None):
    """Scan downloaded episodes for subtitle sidecars without locking the UI.

    v18.2.2 changes this from one long database write transaction into:
    - one quick read-only episode lookup,
    - file-system scanning without a held SQLite write lock,
    - small batched status updates,
    - a safety time limit so network shares cannot make the app appear frozen.
    """
    try:
        max_seconds = float(max_seconds if max_seconds is not None else get_setting("TVManager", "subtitle_scan_max_seconds", "30"))
    except Exception:
        max_seconds = 30.0
    max_seconds = max(5.0, min(max_seconds, 300.0))
    try:
        batch_size = max(10, min(int(batch_size or 50), 250))
    except Exception:
        batch_size = 50
    try:
        max_candidates = int(max_candidates if max_candidates is not None else get_setting("TVManager", "subtitle_scan_max_candidates", "200"))
    except Exception:
        max_candidates = 200
    max_candidates = max(25, min(max_candidates, 2000))
    scan_network = as_bool(get_setting("TVManager", "subtitle_scan_network_paths", "0"))

    with cx(readonly=True) as c:
        if show_id:
            rows=c.execute("""SELECT e.id,e.show_id,e.season,e.episode,e.location,s.name show_name
                              FROM episodes e JOIN shows s ON s.id=e.show_id
                              WHERE e.show_id=? AND e.location IS NOT NULL AND trim(e.location)<>''
                              ORDER BY e.season,e.episode
                              LIMIT ?""",(show_id,max_candidates)).fetchall()
        else:
            rows=c.execute("""SELECT e.id,e.show_id,e.season,e.episode,e.location,s.name show_name
                              FROM episodes e JOIN shows s ON s.id=e.show_id
                              WHERE e.location IS NOT NULL AND trim(e.location)<>''
                              ORDER BY s.name,e.season,e.episode
                              LIMIT ?""",(max_candidates,)).fetchall()
    rows=[dict(r) for r in rows]
    found=missing_count=0;items=[];total=len(rows);processed=0;partial=False;errors=[];updates=[];dir_cache={}
    started=time.monotonic()
    if progress_callback:
        progress_callback({"stage":"Subtitle audit","message":"Preparing fast subtitle scan.","percent":1,"total":total,"processed":0})

    def flush_updates():
        nonlocal updates
        if not updates:
            return
        chunk=updates; updates=[]
        def op():
            with cx() as c:
                c.executemany("UPDATE episodes SET subtitle_status=? WHERE id=?", chunk)
        dbcore.retry(op, attempts=4, first_delay=0.1, max_delay=1.0)

    for idx,e in enumerate(rows, start=1):
        processed=idx
        if time.monotonic()-started > max_seconds:
            partial=True
            errors.append(f"Subtitle scan paused after {int(max_seconds)} seconds to keep TV Manager responsive. Run scan again to continue checking remaining files.")
            break
        if progress_callback and (idx == 1 or idx % 10 == 0 or idx == total):
            progress_callback({
                "stage":"Subtitle audit",
                "message":f"Checking subtitles for {e['show_name']} S{int(e.get('season') or 0):02d}E{int(e.get('episode') or 0):02d}.",
                "percent":max(1,min(98,int(idx/max(1,total)*100))),
                "total":total,"processed":idx-1,"current_show":e["show_name"]
            })
        media=Path(e["location"] or "")
        try:
            if _is_probably_remote_media_path(e.get("location")) and not scan_network:
                status="SkippedRemote"
                updates.append((status,e["id"]))
                if len(items)<500:
                    items.append({"episode_id":e["id"],"show":e["show_name"],"season":e.get("season"),"episode":e.get("episode"),"status":status,"file":str(media)})
                continue
            if not media.exists():
                continue
            parent=str(media.parent).lower()
            stem=media.stem.lower()
            names=dir_cache.get(parent)
            if names is None:
                try:
                    names={p.name.lower() for p in media.parent.iterdir() if p.is_file() and p.suffix.lower() in SUB_EXTS}
                except Exception as exc:
                    names=set(); errors.append(f"{media.parent}: {exc}")
                dir_cache[parent]=names
            present=any(n.startswith(stem+'.') for n in names)
            status="Present" if present else "Missing"
            if present: found+=1
            else: missing_count+=1
            updates.append((status,e["id"]))
            if len(updates)>=batch_size:
                flush_updates()
            if len(items)<500:
                items.append({"episode_id":e["id"],"show":e["show_name"],"season":e.get("season"),"episode":e.get("episode"),"status":status,"file":str(media)})
        except Exception as exc:
            errors.append(f"{e.get('show_name')} S{int(e.get('season') or 0):02d}E{int(e.get('episode') or 0):02d}: {exc}")
    flush_updates()
    result={"checked":found+missing_count,"processed":processed,"present":found,"missing":missing_count,"total":total,"partial":partial,"max_candidates":max_candidates,"network_paths_scanned":scan_network,"errors":errors[:25],"items":items}
    if progress_callback:
        msg="Subtitle audit paused before completion." if partial else "Subtitle audit complete."
        progress_callback({"stage":"Subtitle audit complete" if not partial else "Subtitle audit paused","message":msg,"percent":100 if not partial else max(1,min(99,int(processed/max(1,total)*100))),"total":total,"processed":processed,"succeeded":found,"failed":missing_count,"result":result})
    return result

def upcoming(days=14):
    start = date.today().isoformat()
    end = (date.today()+timedelta(days=days)).isoformat()
    with cx() as c:
        rows = c.execute("""SELECT e.*,s.name show_name,s.poster,s.network
                            FROM episodes e JOIN shows s ON s.id=e.show_id
                            WHERE e.airdate BETWEEN ? AND ?
                            ORDER BY e.airdate,s.name,e.season,e.episode""",(start,end)).fetchall()
    return [dict(r) | {"status_label":status_label(r["status"])} for r in rows]

def missing(limit=500):
    sql = """SELECT e.*,s.name show_name,s.poster,s.network
                            FROM episodes e JOIN shows s ON s.id=e.show_id
                            WHERE lower(COALESCE(e.status,'')) IN ('wanted','failed')
                              AND (e.location IS NULL OR trim(e.location)='')
                              AND (e.airdate IS NULL OR e.airdate<=date('now'))
                              AND COALESCE(e.monitored,1)=1 AND COALESCE(e.ignored,0)=0 AND lower(COALESCE(e.status,''))<>'ignored' AND COALESCE(s.paused,0)=0
                         """ + specials_wanted_sql('e') + """
                            ORDER BY COALESCE(e.airdate,'1900-01-01') DESC,s.name,e.season,e.episode
                            LIMIT ?"""
    with cx() as c:
        rows = c.execute(sql,(limit,)).fetchall()
    return [dict(r) | {"status_label":status_label(r["status"])} for r in rows]

def activity(limit=200):
    with cx() as c:
        rows = c.execute("""SELECT a.*,s.name show_name,e.season,e.episode
                            FROM activity_log a
                            LEFT JOIN shows s ON s.id=a.show_id
                            LEFT JOIN episodes e ON e.id=a.episode_id
                            ORDER BY a.id DESC LIMIT ?""",(limit,)).fetchall()
    return [dict(r) for r in rows]

def activity_filtered(limit=200, offset=0, level=None, event_type=None, q=None, sort="created_at", direction="desc"):
    allowed_sort={"id":"a.id","created_at":"a.created_at","level":"a.level","event_type":"a.event_type","show":"s.name","message":"a.message"}
    sort_sql=allowed_sort.get(str(sort or "created_at"),"a.created_at")
    direction="ASC" if str(direction).lower()=="asc" else "DESC"
    where=[];params=[]
    if level:
        where.append("lower(a.level)=lower(?)");params.append(level)
    if event_type:
        where.append("lower(a.event_type)=lower(?)");params.append(event_type)
    if q:
        where.append("(lower(a.message) LIKE lower(?) OR lower(COALESCE(a.event_type,'')) LIKE lower(?) OR lower(COALESCE(s.name,'')) LIKE lower(?) OR lower(COALESCE(a.data,'')) LIKE lower(?))")
        term=f"%{q}%";params.extend([term,term,term,term])
    where_sql=("WHERE "+" AND ".join(where)) if where else ""
    limit=max(1,min(2000,int(limit or 200)));offset=max(0,int(offset or 0))
    with cx() as c:
        total=c.execute(f"""SELECT COUNT(*) c FROM activity_log a
                            LEFT JOIN shows s ON s.id=a.show_id
                            LEFT JOIN episodes e ON e.id=a.episode_id
                            {where_sql}""",params).fetchone()["c"]
        rows=c.execute(f"""SELECT a.*,s.name show_name,e.season,e.episode
                            FROM activity_log a
                            LEFT JOIN shows s ON s.id=a.show_id
                            LEFT JOIN episodes e ON e.id=a.episode_id
                            {where_sql}
                            ORDER BY {sort_sql} {direction}, a.id {direction}
                            LIMIT ? OFFSET ?""",params+[limit,offset]).fetchall()
        levels=[r["level"] for r in c.execute("SELECT DISTINCT level FROM activity_log WHERE level IS NOT NULL ORDER BY level").fetchall()]
        events=[r["event_type"] for r in c.execute("SELECT DISTINCT event_type FROM activity_log WHERE event_type IS NOT NULL ORDER BY event_type").fetchall()]
    return {"total":total,"limit":limit,"offset":offset,"results":[dict(r) for r in rows],"levels":levels,"event_types":events,"has_more":offset+limit<total}

def downloads(limit=200):
    with cx() as c:
        rows = c.execute("""SELECT d.*,s.name show_name,e.season,e.episode
                            FROM downloads d
                            LEFT JOIN episodes e ON e.id=d.episode_id
                            LEFT JOIN shows s ON s.id=e.show_id
                            ORDER BY d.id DESC LIMIT ?""",(limit,)).fetchall()
    return [dict(r) for r in rows]



def downloader_monitor(limit=200):
    """Return an operator-safe downloader monitoring snapshot.

    This does not expose API keys or passwords. It combines the configured
    downloader summary, queued/download history, handoff candidates, and recent
    downloader log events so the UI can confirm the search-to-client pipeline.
    """
    cfg = downloader_config_public()
    limit=max(1,min(1000,int(limit or 200)))
    with cx() as c:
        downloads_rows=[dict(r) for r in c.execute("""SELECT d.*,s.name show_name,e.season,e.episode
                            FROM downloads d
                            LEFT JOIN episodes e ON e.id=d.episode_id
                            LEFT JOIN shows s ON s.id=e.show_id
                            ORDER BY d.id DESC LIMIT ?""",(limit,)).fetchall()]
        active=c.execute("""SELECT COUNT(*) c FROM downloads
                            WHERE COALESCE(status,'') NOT IN ('Completed','Failed','Superseded')""").fetchone()["c"]
        queued=c.execute("SELECT COUNT(*) c FROM downloads WHERE status='Queued'").fetchone()["c"]
        failed=c.execute("SELECT COUNT(*) c FROM downloads WHERE status='Failed'").fetchone()["c"]
        completed=c.execute("SELECT COUNT(*) c FROM downloads WHERE status IN ('Completed','Downloaded')").fetchone()["c"]
        candidates=[dict(r) for r in c.execute("""SELECT sr.id,s.name show_name,e.season,e.episode,sr.provider,sr.protocol,sr.title,sr.quality,sr.score,sr.created_at
                            FROM search_results sr
                            JOIN episodes e ON e.id=sr.episode_id
                            JOIN shows s ON s.id=e.show_id
                            WHERE COALESCE(sr.rejected_reason,'')='' AND COALESCE(sr.status,'Found') IN ('Found','Accepted')
                            ORDER BY sr.id DESC LIMIT 50""").fetchall()]
        errors=[dict(r) for r in c.execute("""SELECT a.*,s.name show_name,e.season,e.episode
                            FROM activity_log a
                            LEFT JOIN shows s ON s.id=a.show_id
                            LEFT JOIN episodes e ON e.id=a.episode_id
                            WHERE lower(COALESCE(a.event_type,'')) LIKE '%download%'
                               OR lower(COALESCE(a.message,'')) LIKE '%downloader%'
                               OR lower(COALESCE(a.message,'')) LIKE '%sabnzbd%'
                               OR lower(COALESCE(a.message,'')) LIKE '%qbittorrent%'
                            ORDER BY a.id DESC LIMIT 50""").fetchall()]
    configured=[]
    if cfg.get("use_nzbs"):
        method=cfg.get("nzb_method") or "not selected"
        if method=="sabnzbd": configured.append({"type":"nzb","client":"SABnzbd","configured":cfg["sabnzbd"].get("configured"),"host":cfg["sabnzbd"].get("host"),"category":cfg["sabnzbd"].get("category")})
        elif method=="nzbget": configured.append({"type":"nzb","client":"NZBGet","configured":cfg["nzbget"].get("configured"),"host":cfg["nzbget"].get("host"),"category":cfg["nzbget"].get("category")})
        else: configured.append({"type":"nzb","client":method,"configured":method=="blackhole","host":"","category":""})
    if cfg.get("use_torrents"):
        method=cfg.get("torrent_method") or "not selected"
        if method in {"qbittorrent","transmission","deluge"}: configured.append({"type":"torrent","client":method,"configured":cfg["torrent"].get("configured"),"host":cfg["torrent"].get("host"),"category":cfg["torrent"].get("label")})
        else: configured.append({"type":"torrent","client":method,"configured":method=="blackhole","host":"","category":""})
    ready = any(x.get("configured") for x in configured)
    return {
        "ok": True,
        "ready": bool(ready),
        "config": cfg,
        "configured_clients": configured,
        "counts": {"active": active, "queued": queued, "failed": failed, "completed": completed, "handoff_candidates": len(candidates)},
        "downloads": downloads_rows,
        "handoff_candidates": candidates,
        "recent_download_events": errors,
    }


def downloader_readiness_check():
    """Fast configuration/readiness check without exposing secrets."""
    mon=downloader_monitor(limit=25)
    warnings=[]
    cfg=mon.get("config",{})
    if not cfg.get("use_nzbs") and not cfg.get("use_torrents"):
        warnings.append("No NZB or torrent downloading method is enabled.")
    for client in mon.get("configured_clients",[]):
        if not client.get("configured"):
            warnings.append(f"{client.get('client')} is selected but missing host/configuration.")
    return {"ok": True, "ready": mon.get("ready"), "warnings": warnings, "counts": mon.get("counts",{}), "configured_clients": mon.get("configured_clients",[])}

def jobs_public():
    with cx() as c:
        rows = c.execute("SELECT * FROM scheduler_jobs ORDER BY name").fetchall()
    return [dict(r) for r in rows]

def set_automation(enabled):
    set_setting("TVManager","automation_enabled","1" if enabled else "0")
    with cx() as c:
        c.execute("UPDATE scheduler_jobs SET enabled=?", (1 if enabled else 0,))
        c.commit()
    log("automation", "Automation armed" if enabled else "Automation paused")
    return {"enabled":enabled}

def update_job(name, enabled=None, interval=None):
    with cx() as c:
        if enabled is not None:
            c.execute("UPDATE scheduler_jobs SET enabled=? WHERE name=?", (1 if enabled else 0, name))
        if interval is not None:
            c.execute("UPDATE scheduler_jobs SET interval_minutes=? WHERE name=?", (max(1,int(interval)), name))
        c.commit()

def _job_due(r):
    if not r["enabled"]:
        return False
    if not r["last_run"]:
        return True
    try:
        last = datetime.fromisoformat(r["last_run"])
    except Exception:
        return True
    return datetime.now() >= last + timedelta(minutes=r["interval_minutes"])

def _finish_job(name, status, message):
    def write_finish():
        with cx() as c:
            r = c.execute("SELECT interval_minutes FROM scheduler_jobs WHERE name=?", (name,)).fetchone()
            nxt = (datetime.now()+timedelta(minutes=r["interval_minutes"])).replace(microsecond=0).isoformat() if r else None
            c.execute("""UPDATE scheduler_jobs SET last_run=?,next_run=?,last_status=?,last_message=? WHERE name=?""",
                      (now_iso(),nxt,status,str(message)[:1000],name))
            c.commit()
    return dbcore.retry(write_finish, attempts=8)


def poll_sab_downloads():
    host=(get_setting("SABnzbd","sab_host","") or "").rstrip("/")+"/"
    key=get_setting("SABnzbd","sab_apikey","") or ""
    if not host.strip("/"):
        return {"client":"SABnzbd","checked":0,"updated":0,"message":"Not configured"}
    r=requests.get(urljoin(host,"api"),params={"mode":"history","limit":100,"output":"json","apikey":key},timeout=15)
    r.raise_for_status()
    data=r.json()
    slots=(data.get("history") or {}).get("slots") or []
    by_id={}
    for s in slots:
        nzo=s.get("nzo_id") or s.get("nzoid")
        if nzo: by_id[str(nzo)]=s
    updated=0
    with cx() as c:
        rows=c.execute("SELECT * FROM downloads WHERE client='SABnzbd' AND status NOT IN ('Completed','Failed')").fetchall()
        for d in rows:
            if not d["external_id"]: continue
            s=by_id.get(str(d["external_id"]))
            if not s: continue
            st=str(s.get("status") or "").lower()
            if st in {"completed","success"}:
                lifecycle.transition("episode",d["id"],d["status"],"Downloaded",
                                     message="SABnzbd download completed",conn=c,force=True)
                c.execute("UPDATE downloads SET completed_at=CURRENT_TIMESTAMP WHERE id=?",(d["id"],))
                updated+=1
                log("download_completed",f'SABnzbd completed {d["release_name"]}',episode_id=d["episode_id"],conn=c)
            elif st in {"failed"}:
                lifecycle.transition("episode",d["id"],d["status"],"Failed",
                                     message=s.get("fail_message") or "SABnzbd failed",conn=c,force=True)
                c.execute("UPDATE downloads SET error=? WHERE id=?",(s.get("fail_message") or "SABnzbd failed",d["id"]))
                if d["episode_id"]: c.execute("UPDATE episodes SET status='Failed' WHERE id=?",(d["episode_id"],))
                updated+=1
        packs=c.execute("SELECT * FROM season_pack_downloads WHERE client='SABnzbd' AND status NOT IN ('Completed','Failed')").fetchall()
        for pack in packs:
            slot=by_id.get(str(pack["external_id"])) if pack["external_id"] else None
            if not slot:continue
            st=str(slot.get("status") or "").lower()
            if st in {"completed","success"}:
                lifecycle.transition("season_pack",pack["id"],pack["status"],"Downloaded",
                                     message="SABnzbd season pack completed",conn=c,force=True)
                c.execute("UPDATE season_pack_downloads SET progress=1,updated_at=CURRENT_TIMESTAMP WHERE id=?",(pack["id"],))
                updated+=1
            elif st=="failed":
                err=slot.get("fail_message") or "SABnzbd failed"
                lifecycle.transition("season_pack",pack["id"],pack["status"],"Failed",
                                     message=err,conn=c,force=True)
                c.execute("UPDATE season_pack_downloads SET error=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(err,pack["id"]))
                for ep in c.execute("""SELECT episode_id FROM acquisition_episode_links
                                       WHERE acquisition_type='season_pack' AND acquisition_id=?""",(pack["id"],)).fetchall():
                    c.execute("UPDATE episodes SET status='Failed' WHERE id=? AND (location IS NULL OR trim(location)='')",(ep["episode_id"],))
                updated+=1
        c.commit()
    return {"client":"SABnzbd","checked":len(rows)+len(packs),"updated":updated}

def poll_qbit_downloads():
    cfg=downloader_config_public()
    if cfg["torrent_method"]!="qbittorrent" or not cfg["torrent"]["configured"]:
        return {"client":"qBittorrent","checked":0,"updated":0,"message":"Not configured"}
    sess,host=_qbit_session()
    r=sess.get(host+"/api/v2/torrents/info",timeout=15);r.raise_for_status()
    torrents=r.json()
    by_hash={str(t.get("hash") or "").lower():t for t in torrents if t.get("hash")}
    active=sum(1 for t in torrents if str(t.get("state","")).lower() not in {"pausedup","pauseddl","stalledup","stalleddl"})
    complete=sum(1 for t in torrents if float(t.get("progress") or 0)>=1.0)
    updated=0
    with cx() as c:
        rows=c.execute("""SELECT * FROM downloads WHERE client='qBittorrent'
                          AND external_id IS NOT NULL AND trim(external_id)<>''
                          AND status NOT IN ('Completed','Failed')""").fetchall()
        for d in rows:
            t=by_hash.get(str(d["external_id"]).lower())
            if not t:continue
            progress=float(t.get("progress") or 0)
            status="Downloaded" if progress>=1 else "Downloading"
            if status != d["status"]:
                lifecycle.transition("episode",d["id"],d["status"],status,
                                     message=f"qBittorrent progress {progress:.1%}",conn=c,force=True)
            if status=="Downloaded":
                c.execute("UPDATE downloads SET completed_at=CURRENT_TIMESTAMP WHERE id=?",(d["id"],))
            updated+=1
        packs=c.execute("""SELECT * FROM season_pack_downloads WHERE client='qBittorrent'
                           AND external_id IS NOT NULL AND trim(external_id)<>''
                           AND status NOT IN ('Completed','Failed')""").fetchall()
        for pack in packs:
            t=by_hash.get(str(pack["external_id"]).lower())
            if not t:continue
            progress=float(t.get("progress") or 0)
            status="Downloaded" if progress>=1 else "Downloading"
            if status != pack["status"]:
                lifecycle.transition("season_pack",pack["id"],pack["status"],status,
                                     message=f"qBittorrent progress {progress:.1%}",conn=c,force=True)
            c.execute("UPDATE season_pack_downloads SET progress=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                      (progress,pack["id"]));updated+=1
        c.commit()
    return {"client":"qBittorrent","checked":len(torrents),"updated":updated,"active":active,"complete":complete}

def poll_downloaders():
    results=[]
    cfg=downloader_config_public()
    if cfg["use_nzbs"] and cfg["nzb_method"]=="sabnzbd":
        try: results.append(poll_sab_downloads())
        except Exception as e: results.append({"client":"SABnzbd","error":str(e)})
    if cfg["use_torrents"] and cfg["torrent_method"]=="qbittorrent":
        try: results.append(poll_qbit_downloads())
        except Exception as e: results.append({"client":"qBittorrent","error":str(e)})
    from downloader_polling import snapshot, update
    clients=[]
    if cfg["use_nzbs"] and cfg["nzb_method"]=="nzbget":clients.append("NZBGet")
    if cfg["use_torrents"] and cfg["torrent_method"] in {"transmission","deluge"}:clients.append({"transmission":"Transmission","deluge":"Deluge"}[cfg["torrent_method"]])
    for client in clients:
        try:
            result=update(DB,client,snapshot(client,get_setting))
            for failure in result.pop("failures",[]):
                try:advanced.fire_webhooks("failed",failure)
                except Exception:pass
            results.append(result)
        except Exception:results.append({"client":client,"error":"Polling failed; check client availability and configuration"})
    return {"results":results}

def write_show_metadata(show_id, artwork=True, episode_nfo=True):
    with cx() as c:
        show=c.execute("SELECT * FROM shows WHERE id=?",(show_id,)).fetchone()
        if not show: raise ValueError("Show not found")
        episodes=c.execute("SELECT * FROM episodes WHERE show_id=? ORDER BY season,episode",(show_id,)).fetchall()
    if not show["location"]:
        raise ValueError("Show library folder is not configured")
    root=Path(show["location"]); root.mkdir(parents=True,exist_ok=True)
    tvshow_nfo=f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<tvshow>
  <title>{xml_escape(show["name"] or "")}</title>
  <originaltitle>{xml_escape(show["original_name"] or "")}</originaltitle>
  <plot>{xml_escape(show["overview"] or "")}</plot>
  <premiered>{xml_escape(show["first_air_date"] or "")}</premiered>
  <studio>{xml_escape(show["network"] or "")}</studio>
  <genre>{xml_escape(show["genre"] or "")}</genre>
  <status>{xml_escape(show["status"] or "")}</status>
  <uniqueid type="imdb">{xml_escape(show["imdb_id"] or "")}</uniqueid>
  <uniqueid type="tmdb" default="true">{xml_escape(str(show["tmdb_id"] or ""))}</uniqueid>
  <uniqueid type="tvdb">{xml_escape(str(show["tvdb_id"] or ""))}</uniqueid>
</tvshow>
"""
    (root/"tvshow.nfo").write_text(tvshow_nfo,encoding="utf-8")
    written=1
    artwork_saved=False
    if artwork and show["poster"]:
        try:
            r=requests.get(show["poster"],timeout=20,headers={"User-Agent":"TVManager/5.1"})
            r.raise_for_status()
            ext=".jpg"
            (root/"poster.jpg").write_bytes(r.content)
            artwork_saved=True
        except Exception as e:
            log("metadata_artwork_error",f'Poster download failed for {show["name"]}: {e}',"warning",show_id=show_id)
    if episode_nfo:
        for ep in episodes:
            if not ep["location"]: continue
            media=Path(ep["location"])
            if not media.exists(): continue
            nfo=media.with_suffix(".nfo")
            body=f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<episodedetails>
  <title>{xml_escape(ep["name"] or "")}</title>
  <showtitle>{xml_escape(show["name"] or "")}</showtitle>
  <season>{ep["season"]}</season>
  <episode>{ep["episode"]}</episode>
  <aired>{xml_escape(ep["airdate"] or "")}</aired>
</episodedetails>
"""
            nfo.write_text(body,encoding="utf-8");written+=1
    log("metadata_written",f'{show["name"]}: wrote {written} NFO files',show_id=show_id,
        data={"artwork_saved":artwork_saved})
    return {"ok":True,"root":str(root),"nfo_files":written,"artwork_saved":artwork_saved}


def run_job(name):
    if name in _RUNNING:
        return {"ok":False,"message":"Job is already running in this process"}
    lease_minutes=15
    if not scheduler_guard.acquire(name,lease_minutes):
        return {"ok":False,"message":"Job is already leased by another TV Manager process"}
    lease_stop=threading.Event()
    def lease_heartbeat():
        while not lease_stop.wait(60):
            if not scheduler_guard.renew(name,lease_minutes):
                break
    threading.Thread(target=lease_heartbeat,daemon=True,name=f"TVManagerLease-{name}").start()
    _RUNNING.add(name)
    run_id=None
    try:
        with cx() as c:
            cur=c.execute("INSERT INTO scheduler_runs(job_name,status) VALUES(?,'Running')",(name,))
            run_id=cur.lastrowid;c.commit()
        if name == "recent_search":
            result = run_search_job("recent")
            msg = json.dumps(result)
        elif name == "backlog_search":
            result = run_search_job("backlog")
            msg = json.dumps(result)
        elif name == "download_status":
            result = poll_downloaders()
            msg = json.dumps(result)
        elif name == "subtitle_jobs":
            queued=sync.enqueue_preferred_subtitles()
            result = sync.run_subtitle_jobs(limit=20)
            result["queued_by_language"]=queued
            msg = json.dumps(result)
        elif name == "watched_sync":
            result={"servers":[]}
            for server in advanced.media_servers():
                try:
                    if (server.get("kind") or "").lower() in {"plex","jellyfin","emby"}:
                        result["servers"].append(sync.sync_watched(server["id"]))
                except Exception as ex:
                    result["servers"].append({"server_id":server.get("id"),"error":str(ex)})
            msg=json.dumps(result)
        elif name == "post_processing":
            configured=as_bool(get_setting("General","process_automatically","0"),False)
            simulation=as_bool(get_setting("TVManager","simulation_mode","0"),False)
            live=configured and not simulation
            result = scan_postprocess(dry_run=not live)
            result["scheduled_live"]=live
            result["process_automatically"]=configured
            result["simulation_mode"]=simulation
            msg = json.dumps(result)
        elif name == "metadata_refresh":
            result = metadata_service.refresh_batch()
            msg = json.dumps(result)
        elif name == "missing_metadata":
            result = metadata_service.refresh_missing_metadata(limit=as_int(get_setting("TVManager","metadata_missing_limit","200"),200))
            msg = json.dumps(result)
        elif name == "artwork_refresh":
            result = metadata_service.refresh_artwork(limit=as_int(get_setting("TVManager","artwork_refresh_limit","200"),200), include_episodes=True)
            msg = json.dumps(result)
        elif name == "library_health_scan":
            result = library_maintenance.library_health_report(DB, duplicate_limit=25, sample_limit=25)
            msg = json.dumps(result)
        elif name == "database_protection":
            result = database_safety.protect_now(reason="scheduled", include_config=True, include_secrets=False)
            msg = json.dumps(result)
        else:
            raise ValueError("Unknown job")
        _finish_job(name,"OK",msg)
        if run_id:
            def finish_run_ok():
                with cx() as c:
                    c.execute("UPDATE scheduler_runs SET finished_at=CURRENT_TIMESTAMP,status='OK',message=? WHERE id=?",(msg[:2000],run_id));c.commit()
            dbcore.retry(finish_run_ok, attempts=8)
        return {"ok":True,"result":result}
    except Exception as e:
        try:
            _finish_job(name,"Error",str(e))
        except Exception as finish_error:
            log("scheduler_finish_error", f"{name}: could not update scheduler status: {finish_error}", "error")
        if run_id:
            def finish_run_error():
                with cx() as c:
                    c.execute("UPDATE scheduler_runs SET finished_at=CURRENT_TIMESTAMP,status='Error',message=? WHERE id=?",(str(e)[:2000],run_id));c.commit()
            try:
                dbcore.retry(finish_run_error, attempts=8)
            except Exception as run_error:
                log("scheduler_run_finish_error", f"{name}: could not update run history: {run_error}", "error")
        log("scheduler_error", f"{name}: {e}", "error")
        return {"ok":False,"error":str(e)}
    finally:
        _RUNNING.discard(name)
        lease_stop.set()
        scheduler_guard.release(name)

def scheduler_loop():
    while not _STOP.wait(30):
        if not as_bool(get_setting("TVManager","automation_enabled","0")):
            continue
        with cx() as c:
            jobs = c.execute("SELECT * FROM scheduler_jobs WHERE enabled=1").fetchall()
        for r in jobs:
            if _job_due(r):
                threading.Thread(target=run_job,args=(r["name"],),daemon=True).start()

def start_scheduler():
    if getattr(start_scheduler, "_started", False):
        return
    start_scheduler._started = True
    threading.Thread(target=scheduler_loop, daemon=True, name="TVManagerScheduler").start()

def episode_pattern(path):
    name = Path(path).name
    m = re.search(r"(?i)\bS(\d{1,2})E(\d{1,3})\b", name)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(?i)\b(\d{1,2})x(\d{1,3})\b", name)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None

_EPISODE_MARKER_RE = re.compile(r"(?i)(?:^|[\s._\-\[\(])(?:S\d{1,2}E\d{1,3}|\d{1,2}x\d{1,3})(?:\b|[\s._\-\]\)])")

def _normalize_release_title(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()

def _release_prefixes_for_match(path):
    """Return normalized title prefixes before SxxEyy/1xYY from file/folder names.

    Post-processing must not match short show names by arbitrary substring.
    Examples that must be rejected:
      * Friends.from.College.S01E03 -> show From
      * Friends.S03E10...          -> show ER
    The only reliable automatic match is the title segment before the episode
    marker, preferably from the file name and then from the release folder.
    """
    raw_path = str(path)
    # Accept both Windows and POSIX paths even when tests/tools run on Linux.
    path_parts = [part for part in re.split(r"[\\/]+", raw_path) if part]
    file_name = path_parts[-1] if path_parts else Path(path).name
    raw_names = [Path(file_name).stem]
    if len(path_parts) > 1:
        raw_names.append(path_parts[-2])
    else:
        parent = Path(path).parent.name
        if parent:
            raw_names.append(parent)
    prefixes = []
    seen = set()
    for source, raw in (("file", raw_names[0]), ("folder", raw_names[1] if len(raw_names) > 1 else "")):
        if not raw:
            continue
        m = _EPISODE_MARKER_RE.search(raw)
        prefix = raw[:m.start()] if m else raw
        norm = _normalize_release_title(prefix)
        if norm and norm not in seen:
            prefixes.append({"source": source, "raw": prefix.strip(" ._-"), "normalized": norm})
            seen.add(norm)
    return prefixes

def _show_match_names(show):
    names = [show.get("name") or ""]
    aliases = show.get("aliases") or []
    if isinstance(aliases, str):
        aliases = [aliases]
    names.extend(aliases)
    out = []
    seen = set()
    for raw in names:
        norm = _normalize_release_title(raw)
        if norm and norm not in seen:
            out.append({"raw": str(raw), "normalized": norm, "token_count": len(norm.split()), "char_count": len(norm.replace(" ", ""))})
            seen.add(norm)
    return out

def _score_postprocess_show_match(show, path):
    prefixes = _release_prefixes_for_match(path)
    if not prefixes:
        return None
    best = None
    for name in _show_match_names(show):
        norm = name["normalized"]
        one_token = name["token_count"] == 1
        short_title = one_token or name["char_count"] <= 5
        for prefix in prefixes:
            pnorm = prefix["normalized"]
            score = None
            reason = None
            confidence = None
            if pnorm == norm:
                score = 10000 + name["char_count"]
                reason = f"exact {prefix['source']} title prefix"
                confidence = "high"
            elif not short_title and pnorm.startswith(norm + " "):
                # Longer multi-word titles may have release qualifiers after the
                # show name, such as country/year tags. This remains lower than
                # exact so a better title wins.
                score = 7000 + name["char_count"]
                reason = f"{prefix['source']} title prefix starts with show name"
                confidence = "medium"
            elif not short_title and (" " + norm + " ") in (" " + pnorm + " "):
                # Last-resort for longer aliases only. Never use substring-only
                # matching for one-word shows like FROM, ER, YOU, or IT.
                score = 5200 + name["char_count"]
                reason = f"long title token match in {prefix['source']} prefix"
                confidence = "low"
            if score is not None:
                item = {"show": show, "score": score, "confidence": confidence, "reason": reason,
                        "matched_title": name["raw"], "release_prefix": prefix["raw"],
                        "release_prefix_source": prefix["source"]}
                if best is None or item["score"] > best["score"]:
                    best = item
    return best

def _choose_postprocess_show(shows, path):
    matches = [m for m in (_score_postprocess_show_match(sh, path) for sh in shows) if m]
    if not matches:
        return None, "No show title matched the release prefix before SxxEyy/1xYY."
    matches.sort(key=lambda x: x["score"], reverse=True)
    best = matches[0]
    if best["score"] < 7000:
        return None, f"Low-confidence show match blocked: {best['show'].get('name')} matched by {best['reason']}."
    if len(matches) > 1 and matches[1]["score"] >= best["score"] - 10:
        return None, f"Ambiguous show match blocked between {best['show'].get('name')} and {matches[1]['show'].get('name')}."
    return best, None

def scan_postprocess(dry_run=True, limit=300, root_override=None, selected_sources=None, process_method_override=None, progress_callback=None):
    import media_operations
    args=(dry_run,limit,root_override,selected_sources,process_method_override,progress_callback)
    if dry_run:return _scan_postprocess(*args)
    with media_operations.exclusive(BASE):return _scan_postprocess(*args)


def _scan_postprocess(dry_run=True, limit=300, root_override=None, selected_sources=None, process_method_override=None, progress_callback=None):
    """Scan/process completed TV downloads.

    root_override lets an operator temporarily process another completed-downloads
    directory without changing the saved SickChill-style tv_download_dir.
    selected_sources limits processing to paths chosen from a preview, giving the
    UI a safe preview/apply workflow instead of blindly processing everything.
    """
    root = ops.map_path(root_override or get_setting("General","tv_download_dir","") or "")
    selected_sources = set(str(x) for x in (selected_sources or []) if str(x).strip())
    result = {"root":root,"dry_run":dry_run,"files":0,"matched":0,"unmatched":0,
              "blocked":0,"upgrades":0,"actions":[],"media_refresh":[],"unmatched_details":[],
              "selected_sources":len(selected_sources)}
    if not root or not Path(root).exists():
        result["message"] = "Post-processing folder is not reachable from this computer."
        return result

    if progress_callback:
        progress_callback({"stage":"Post-processing scan","message":"Walking completed-download folder.","percent":1,"processed":0,"total":limit})
    files=[]
    walked=0
    for p in Path(root).rglob("*"):
        walked+=1
        if progress_callback and walked % 200 == 0:
            progress_callback({"stage":"Post-processing scan","message":f"Scanning folder entries: {walked:,} checked, {len(files):,} media files found.","percent":min(35, max(2, int(len(files)/max(1,limit)*35))),"processed":len(files),"total":limit})
        if p.is_file() and p.suffix.lower() in MEDIA_EXTS:
            if selected_sources and str(p) not in selected_sources:
                continue
            files.append(p)
            if len(files)>=limit: break
    result["files"]=len(files)
    if progress_callback:
        progress_callback({"stage":"Post-processing match","message":f"Matching {len(files):,} media files to shows and episodes.","percent":40,"processed":0,"total":len(files)})

    with cx() as c:
        shows=[dict(r) for r in c.execute("""SELECT id,name,location,season_folders,scene_numbering
                           FROM shows""").fetchall()]
        alias_rows=c.execute("""SELECT show_id, alias FROM scene_mappings
                                WHERE alias IS NOT NULL AND trim(alias)<>''""").fetchall()
    with cx() as c:
        alias_rows=list(alias_rows)+list(c.execute("SELECT show_id,exception_name AS alias FROM scene_exceptions WHERE trim(exception_name)<>''"))
    aliases_by_show={}
    for r in alias_rows:
        aliases_by_show.setdefault(r["show_id"], []).append(r["alias"])
    for sh in shows:
        sh["aliases"] = aliases_by_show.get(sh["id"], [])

    touched_shows=set()
    for idx,p in enumerate(files, start=1):
        if progress_callback and (idx == 1 or idx % 10 == 0 or idx == len(files)):
            base = 40 + int((idx / max(1, len(files))) * (55 if dry_run else 45))
            progress_callback({"stage":"Post-processing preview" if dry_run else "Post-processing apply", "message":f"Evaluating {p.name}", "percent":min(95,base), "processed":idx-1, "total":len(files), "current_file":str(p)})
        pairs=advanced.split_multi_episode(p.name)
        if not pairs:
            single=episode_pattern(p);pairs=[single] if single else []
        if not pairs:
            result["unmatched"]+=1
            result["unmatched_details"].append({"source":str(p),"reason":"No episode number found (expected SxxEyy or 1xYY). Movies and unnumbered files cannot be processed as TV episodes."})
            continue

        match, match_error = _choose_postprocess_show(shows, p)
        if not match:
            result["unmatched"]+=1
            result.setdefault("unmatched_details",[]).append({"source":str(p),"reason":match_error})
            continue
        show=match["show"]
        if not str(show.get("location") or "").strip():
            result["matched"]+=1
            result["blocked"]+=1
            result["actions"].append({"source":str(p),"destination":"Library folder required","show":show["name"],"show_id":show["id"],"season":pairs[0][0],"episodes":[pair[1] for pair in pairs],"blocked":"Library folder required. Set the destination folder for this show, then preview again.","match_confidence":match["confidence"],"match_reason":match["reason"]})
            continue

        episode_rows=[]
        with cx() as c:
            for season,epno in pairs:
                if show.get("scene_numbering"):
                    import scene_sync
                    matched=scene_sync.episode_rows(c,show["id"],season,epno)
                else:matched=c.execute("SELECT * FROM episodes WHERE show_id=? AND season=? AND episode=?",(show["id"],season,epno)).fetchall()
                for ep in matched:
                    if not any(existing["id"]==ep["id"] for existing in episode_rows):episode_rows.append(ep)
        if not episode_rows:
            result["unmatched"]+=1
            result["unmatched_details"].append({"source":str(p),"reason":f"Show matched {show['name']}, but the episode is missing from its metadata. Refresh show metadata, then preview again."})
            continue

        season=episode_rows[0]["season"]
        incoming_quality=infer_quality(p.name)
        # Match the newest acquisition, if any, to preserve the provider release name.
        acquisitions={}
        with cx() as c:
            for e in episode_rows:
                d=c.execute("""SELECT * FROM downloads WHERE episode_id=?
                               AND status NOT IN ('Completed','Superseded')
                               ORDER BY id DESC LIMIT 1""",(e["id"],)).fetchone()
                if d: acquisitions[e["id"]]=d

        # Evaluate every existing file before moving anything.
        blocked_reason=None
        for e in episode_rows:
            if e["location"] and Path(e["location"]).exists():
                d=acquisitions.get(e["id"])
                new_release=d["release_name"] if d else p.stem
                allowed,reason=lifecycle.replacement_allowed(e["quality"],e["release_name"],
                                                             incoming_quality,new_release)
                if not allowed:
                    blocked_reason=reason;break

        rename_enabled=as_bool(get_setting("General","rename_episodes","1"),True)
        naming_pattern=get_setting("General","naming_pattern","Season %0S/%SN - S%0SE%0E - %EN")
        eps_for_name=[dict(e) for e in episode_rows]
        dest=naming.configured_destination(
            ops.map_path(show["location"]),show["name"],eps_for_name,p.name,
            naming_pattern,rename_enabled,bool(show["season_folders"]))
        dest_dir=dest.parent

        action={"source":str(p),"destination":str(dest),"show":show["name"],"show_id":show["id"],
                "season":season,"episodes":[e["episode"] for e in episode_rows],
                "episode_ids":[e["id"] for e in episode_rows],"quality":incoming_quality,
                "rename_enabled":rename_enabled,"naming_pattern":naming_pattern,
                "renamed":p.name!=dest.name,
                "match_confidence":match.get("confidence"),
                "match_reason":match.get("reason"),
                "matched_title":match.get("matched_title"),
                "release_prefix":match.get("release_prefix")}
        if match.get("confidence") != "high":
            action["review_note"] = "Review this match before processing."

        if blocked_reason:
            action["blocked"]=blocked_reason
            result["actions"].append(action);result["blocked"]+=1
            for e in episode_rows:
                d=acquisitions.get(e["id"])
                if d:
                    try:lifecycle.transition("episode",d["id"],d["status"],"Blocked",
                                             message=blocked_reason,force=True)
                    except Exception:pass
            log("upgrade_blocked",f'{show["name"]}: {blocked_reason}',"warning",
                show_id=show["id"],data=action)
            continue

        result["actions"].append(action)
        result["matched"]+=len(episode_rows)
        if dry_run:continue

        replacement_ids=[]
        try:
            # Stage old files into managed trash before replacing them.
            staged_old_paths=set()
            for e in episode_rows:
                if not e["location"] or e["location"] in staged_old_paths:continue
                old=Path(e["location"])
                if old.exists() and old.is_file():
                    d=acquisitions.get(e["id"])
                    new_release=d["release_name"] if d else p.stem
                    staged=lifecycle.stage_replacement(e,p,new_release,incoming_quality)
                    if not staged.get("allowed"):
                        raise ValueError(staged.get("reason") or "Replacement blocked")
                    if staged.get("replacement_id"):
                        replacement_ids.append(staged["replacement_id"])
                        result["upgrades"]+=1
                    staged_old_paths.add(e["location"])

            for e in episode_rows:
                d=acquisitions.get(e["id"])
                if d:
                    lifecycle.transition("episode",d["id"],d["status"],"Importing",
                                         message="Post-processing media file",force=True)

            method=(process_method_override or get_setting("General","process_method","move") or "move").lower()
            if method not in {"move","copy","hardlink","hard link"}:
                method="move"
            move_associated=as_bool(get_setting("General","move_associated_files","1"),True)
            sidecars=naming.associated_destinations(p,dest) if move_associated else []
            dest_dir.mkdir(parents=True,exist_ok=True)
            if dest.exists() and dest.resolve()!=p.resolve():
                # The current file should already have been staged. Never silently overwrite an unrelated file.
                raise FileExistsError(f"Destination already exists: {dest}")
            if method=="copy":shutil.copy2(p,dest)
            elif method in {"hardlink","hard link"}:os.link(p,dest)
            else:shutil.move(str(p),str(dest))

            associated_moved=[]
            for src_side,dst_side in sidecars:
                try:
                    dst_side.parent.mkdir(parents=True,exist_ok=True)
                    if dst_side.exists():continue
                    if method=="copy":shutil.copy2(src_side,dst_side)
                    elif method in {"hardlink","hard link"}:os.link(src_side,dst_side)
                    else:shutil.move(str(src_side),str(dst_side))
                    associated_moved.append({"source":str(src_side),"destination":str(dst_side)})
                except Exception as side_ex:
                    log("associated_file_error",str(side_ex),"warning",show_id=show["id"])

            size=dest.stat().st_size
            with cx() as c:
                for e in episode_rows:
                    d=acquisitions.get(e["id"])
                    release_name=d["release_name"] if d else p.stem
                    c.execute("""UPDATE episodes SET location=?,status='Downloaded',file_size=?,
                                 quality=?,release_name=? WHERE id=?""",
                              (str(dest),size,incoming_quality,release_name,e["id"]))
                    c.execute("""INSERT INTO postprocess_history(
                                 source_path,destination_path,show_id,episode_id,method,status,message)
                                 VALUES(?,?,?,?,?,'OK','Processed')""",
                              (str(p),str(dest),show["id"],e["id"],method))
                    if d:
                        lifecycle.transition("episode",d["id"],"Importing","Completed",
                                             message="Episode imported into library",
                                             details={"path":str(dest)},conn=c,force=True)
                c.commit()

            for rid in replacement_ids:lifecycle.complete_replacement(rid,dest)
            action["associated_files"]=associated_moved
            try:
                action["fingerprint"]=integrity.cache_fingerprint(dest,episode_rows[0]["id"])["fingerprint"]
            except Exception as fp_ex:
                action["fingerprint_error"]=str(fp_ex)
            touched_shows.add(show["id"])

            for e in episode_rows:
                payload={"show":show["name"],"season":e["season"],"episode":e["episode"],
                         "path":str(dest),"method":method,"quality":incoming_quality}
                log("post_processed",f'{show["name"]} S{e["season"]:02d}E{e["episode"]:02d} processed',
                    show_id=show["id"],episode_id=e["id"],data=payload)
                try:advanced.fire_webhooks("downloaded",payload)
                except Exception:pass

            try:
                completed=release.mark_pack_processed(show["id"],season)
                if completed:
                    log("season_pack_completed",f'{show["name"]} Season {season} pack fully imported',
                        show_id=show["id"])
            except Exception as ex:
                log("season_pack_finalize_error",str(ex),"warning",show_id=show["id"])

        except Exception as ex:
            # Restore staged originals if the replacement import fails.
            for rid in reversed(replacement_ids):
                try:lifecycle.rollback_replacement(rid)
                except Exception as rollback_ex:
                    log("upgrade_rollback_error",str(rollback_ex),"error",show_id=show["id"])
            for e in episode_rows:
                d=acquisitions.get(e["id"])
                if d:
                    try:lifecycle.transition("episode",d["id"],d["status"],"Failed",
                                             message=str(ex),force=True)
                    except Exception:pass
            result.setdefault("errors",[]).append({"file":str(p),"error":str(ex)})
            log("postprocess_error",f'{show["name"]}: {ex}',"error",show_id=show["id"])
            continue

    if not dry_run and touched_shows and as_bool(get_setting("TVManager","refresh_media_servers_after_process","1")):
        for show_id in sorted(touched_shows):
            for server in advanced.media_servers():
                if not server.get("enabled"):continue
                try:
                    rr=advanced.refresh_media_server_target(server["id"],show_id=show_id)
                    result["media_refresh"].append({"show_id":show_id,"server":server["name"],**rr})
                except Exception as ex:
                    result["media_refresh"].append({"show_id":show_id,"server":server.get("name"),"error":str(ex)})
                    log("media_refresh_error",str(ex),"warning",show_id=show_id)
    return result
