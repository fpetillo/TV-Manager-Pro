import dbcore
import db_doctor
import migrations
import lifecycle
import naming
import integrity
import scheduler_guard
import security
import metadata_service
import tmdb_client
import sickchill_importer
import library_maintenance
import import_recovery
import configparser, json, os, shutil, sqlite3, io, zipfile, threading, uuid, traceback, sys
from datetime import date, datetime
from pathlib import Path
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file, session, redirect, url_for, g
from werkzeug.utils import secure_filename
import engine
import advanced
import ops
import intelligence
import completion
import production
import release
import sync
import support_routes
import operator_experience
import trakt_client
import database_safety
import job_center
import sickchill_parity
import help_content
import episode_rules

BASE=Path(__file__).resolve().parent
APP_VERSION=(BASE/"VERSION").read_text(encoding="utf-8").strip() if (BASE/"VERSION").exists() else "development"
load_dotenv(BASE/".env")
DB=BASE/"tvmanager.db"
IMPORTS=BASE/"imports"; IMPORTS.mkdir(exist_ok=True)
IMPORT_JOBS: dict[str, dict] = {}
IMPORT_JOBS_LOCK = threading.RLock()
app=Flask(__name__)
app.secret_key=security.session_secret()
app.config["MAX_CONTENT_LENGTH"]=512*1024*1024
app.config["SESSION_COOKIE_HTTPONLY"]=True
app.config["SESSION_COOKIE_SAMESITE"]="Lax"
app.config["SESSION_COOKIE_SECURE"]=str(os.getenv("TVMANAGER_HTTPS","0")).lower() in {"1","true","yes","on"}

# Register dependable support routes before the main UI routes.
# This guarantees /about, /library-health, /routes and version APIs exist
# even if a later template/static route fails.
support_routes.register_support_routes(app, BASE, lambda: APP_VERSION)

BACKUPS=BASE/"backups"; BACKUPS.mkdir(exist_ok=True)
MANAGED_TRASH=BASE/"managed_trash"; MANAGED_TRASH.mkdir(exist_ok=True)

# Repair old or partially migrated databases before any startup component
# creates indexes or queries feature-era columns. This is intentionally
# early and idempotent so upgrades over existing installs are safe.
#
# PyInstaller imports/analyzes server.py during the Windows EXE build.  Do not
# touch the operator's live tvmanager.db during packaging; build-exe.ps1 sets
# TVMANAGER_BUILDING_EXE=1 for that process.
if str(os.getenv("TVMANAGER_BUILDING_EXE", "")).lower() not in {"1", "true", "yes", "on"}:
    try:
        if DB.exists():
            database_safety.backup_database(DB, reason=f"pre-startup-v{APP_VERSION}", retention=30)
        db_doctor.repair(DB)
    except Exception as exc:
        raise RuntimeError(
            "TV Manager cannot start because tvmanager.db failed the startup "
            "database safety check. The database may be malformed/corrupt. "
            "Stop TV Manager, preserve this file, and restore a known-good "
            "backup from backups\\safe, backups\\, or a tvmanager-before-*.db "
            "copy before starting again. Details: " + str(exc)
        ) from exc

def backup_before_upgrade():
    if not DB.exists():
        return None
    marker=BACKUPS/"v4.1-backup.done"
    if marker.exists():
        return None
    result=database_safety.backup_database(DB, reason="pre-upgrade-v4.1", retention=30)
    backup_path=result.get("backup") or result.get("preserved_unverified_copy")
    marker.write_text(str(backup_path or "backup-attempt-recorded"),encoding="utf-8")
    return Path(backup_path) if backup_path else None



@app.context_processor
def inject_app_version():
    return {"app_version": APP_VERSION}

def cx(path=None, readonly=False):
    return dbcore.connect(path or DB, wal=(path is None), readonly=readonly)

def _write_import_verification_report(payload):
    diag=BASE/"diagnostics"
    diag.mkdir(exist_ok=True)
    report=diag/"last-import-verification.json"
    report.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return report

def _active_import_verification(extra=None):
    # Fresh post-import verification can briefly collide with SQLite cleanup on
    # Windows. Retry instead of surfacing a misleading database-locked failure.
    import time
    last_error = None
    for _ in range(10):
        try:
            data=import_recovery.active_counts(DB)
            if extra:
                data.update(extra)
            data["verification_error"] = None
            return data
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            last_error = str(exc)
            time.sleep(0.35)
    data={"database": str(DB), "exists": DB.exists(), "shows": 0, "episodes": 0, "import_runs": 0, "imported_show_audit_rows": 0, "verification_error": last_error}
    if extra:
        data.update(extra)
    return data

def _ensure_columns(c, table, required):
    existing = {r["name"] for r in c.execute(f'PRAGMA table_info("{table}")').fetchall()}
    for name, definition in required.items():
        if name not in existing:
            c.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')


def _shows_tmdb_is_not_null(c):
    for r in c.execute('PRAGMA table_info("shows")').fetchall():
        if r["name"] == "tmdb_id":
            return bool(r["notnull"])
    return False

def _rebuild_shows_nullable_tmdb(c):
    # Earlier versions created shows.tmdb_id as NOT NULL.
    # SickChill imports may not have a TMDb ID, so rebuild while preserving IDs/data.
    old_cols = [r["name"] for r in c.execute('PRAGMA table_info("shows")').fetchall()]
    desired_cols = [
        "id","tmdb_id","imdb_id","tvdb_id","legacy_indexer_id","name","original_name",
        "first_air_date","overview","poster","vote_average","location","network","genre",
        "quality","paused","anime","status","legacy_data","added_at"
    ]

    c.execute("PRAGMA foreign_keys=OFF")
    c.execute('ALTER TABLE "shows" RENAME TO "shows_old_migrate"')
    c.execute("""
        CREATE TABLE shows(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tmdb_id INTEGER UNIQUE,
          imdb_id TEXT,
          tvdb_id INTEGER,
          legacy_indexer_id INTEGER,
          name TEXT NOT NULL,
          original_name TEXT,
          first_air_date TEXT,
          overview TEXT,
          poster TEXT,
          vote_average REAL,
          location TEXT,
          network TEXT,
          genre TEXT,
          quality TEXT,
          paused INTEGER DEFAULT 0,
          anime INTEGER DEFAULT 0,
          status TEXT DEFAULT 'Wanted',
          legacy_data TEXT,
          added_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    common = [col for col in desired_cols if col in old_cols]
    if common:
        cols = ",".join(f'"{x}"' for x in common)
        c.execute(f'INSERT INTO "shows" ({cols}) SELECT {cols} FROM "shows_old_migrate"')

    c.execute('DROP TABLE "shows_old_migrate"')
    c.execute("PRAGMA foreign_keys=ON")

def init():
    with cx() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS shows(
          id INTEGER PRIMARY KEY AUTOINCREMENT, tmdb_id INTEGER UNIQUE, imdb_id TEXT,
          tvdb_id INTEGER, legacy_indexer_id INTEGER, name TEXT NOT NULL, original_name TEXT,
          first_air_date TEXT, overview TEXT, poster TEXT, vote_average REAL, location TEXT,
          network TEXT, genre TEXT, quality TEXT, paused INTEGER DEFAULT 0, anime INTEGER DEFAULT 0,
          status TEXT DEFAULT 'Wanted', legacy_data TEXT, added_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS episodes(
          id INTEGER PRIMARY KEY AUTOINCREMENT, show_id INTEGER NOT NULL, season INTEGER NOT NULL,
          episode INTEGER NOT NULL, name TEXT, airdate TEXT, status TEXT, location TEXT,
          file_size INTEGER, release_name TEXT, quality TEXT, legacy_data TEXT,
          overview TEXT, still_url TEXT, still_path TEXT, tmdb_episode_id INTEGER, metadata_updated_at TEXT,
          monitored INTEGER DEFAULT 1, ignored INTEGER DEFAULT 0, ignored_reason TEXT, ignored_at TEXT, ignored_source TEXT, managed_note TEXT,
          UNIQUE(show_id,season,episode));
        CREATE TABLE IF NOT EXISTS import_runs(
          id INTEGER PRIMARY KEY AUTOINCREMENT, source_name TEXT, shows_found INTEGER DEFAULT 0,
          shows_imported INTEGER DEFAULT 0, shows_skipped INTEGER DEFAULT 0,
          episodes_found INTEGER DEFAULT 0, episodes_imported INTEGER DEFAULT 0,
          episodes_skipped INTEGER DEFAULT 0, imported_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS settings(
          section TEXT NOT NULL,
          name TEXT NOT NULL,
          value TEXT,
          is_secret INTEGER NOT NULL DEFAULT 0,
          source TEXT NOT NULL DEFAULT 'app',
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY(section,name));
        CREATE TABLE IF NOT EXISTS legacy_identity_map(
          source_name TEXT NOT NULL, legacy_show_id INTEGER, tvmanager_show_id INTEGER NOT NULL,
          tvdb_id INTEGER, imdb_id TEXT, show_name TEXT, imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY(source_name, legacy_show_id));
        CREATE TABLE IF NOT EXISTS import_run_details(
          id INTEGER PRIMARY KEY AUTOINCREMENT, import_run_id INTEGER, source_name TEXT NOT NULL,
          item_type TEXT NOT NULL, source_id TEXT, tvmanager_id INTEGER, action TEXT NOT NULL,
          message TEXT, details_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)

        # Upgrade databases created by earlier app versions without losing data.
        _ensure_columns(c, "shows", {
            "imdb_id": "TEXT",
            "tvdb_id": "INTEGER",
            "legacy_indexer_id": "INTEGER",
            "original_name": "TEXT",
            "first_air_date": "TEXT",
            "overview": "TEXT",
            "poster": "TEXT",
            "vote_average": "REAL",
            "location": "TEXT",
            "network": "TEXT",
            "genre": "TEXT",
            "quality": "TEXT",
            "paused": "INTEGER DEFAULT 0",
            "anime": "INTEGER DEFAULT 0",
            "status": "TEXT DEFAULT 'Wanted'",
            "legacy_data": "TEXT",
            "added_at": "TEXT",
        })

        _ensure_columns(c, "episodes", {
            # Core columns required before startup status normalization and route registration.
            # Existing user databases from early builds may have only id/show_id/season/episode.
            "name": "TEXT",
            "airdate": "TEXT",
            "status": "TEXT DEFAULT 'Wanted'",
            "location": "TEXT",
            "file_size": "INTEGER",
            "release_name": "TEXT",
            "quality": "TEXT",
            "legacy_data": "TEXT",
            "overview": "TEXT",
            "still_url": "TEXT",
            "still_path": "TEXT",
            "tmdb_episode_id": "INTEGER",
            "metadata_updated_at": "TEXT",
            "monitored": "INTEGER DEFAULT 1",
            "ignored": "INTEGER DEFAULT 0",
            "ignored_reason": "TEXT",
            "ignored_at": "TEXT",
            "ignored_source": "TEXT",
            "managed_note": "TEXT",
        })

        # Older v2 databases may still have tmdb_id defined NOT NULL.
        # Rebuild the table once so SickChill shows without TMDb IDs can import.
        if _shows_tmdb_is_not_null(c):
            _rebuild_shows_nullable_tmdb(c)

        c.execute("CREATE INDEX IF NOT EXISTS idx_shows_imdb ON shows(imdb_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_shows_tvdb ON shows(tvdb_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_shows_legacy ON shows(legacy_indexer_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_shows_name_nocase ON shows(name COLLATE NOCASE)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_shows_status ON shows(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_episodes_show_season ON episodes(show_id, season)")

def pick(row,*names):
    keys={k.lower():k for k in row.keys()}
    for n in names:
        if n.lower() in keys: return row[keys[n.lower()]]
    return None

def i(v):
    try: return int(v) if v not in (None,"") else None
    except: return None

def s(v): return None if v is None else str(v)

def detect(path):
    with cx(path) as c:
        tables=[r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        low={x.lower():x for x in tables}
        st=next((low[x] for x in ("tv_shows","shows","tvshows") if x in low),None)
        et=next((low[x] for x in ("tv_episodes","episodes","tvepisodes") if x in low),None)
        cols=lambda t:[r["name"] for r in c.execute(f'PRAGMA table_info("{t}")')] if t else []
        return {"tables":tables,"show_table":st,"episode_table":et,"show_columns":cols(st),"episode_columns":cols(et)}

def existing(c,tmdb=None,imdb=None,tvdb=None,legacy=None,name=None):
    for col,val in (("tmdb_id",tmdb),("imdb_id",imdb),("tvdb_id",tvdb),("legacy_indexer_id",legacy)):
        if val not in (None,""):
            r=c.execute(f"SELECT id FROM shows WHERE {col}=? LIMIT 1",(val,)).fetchone()
            if r:return r["id"]
    if name:
        r=c.execute("SELECT id FROM shows WHERE lower(name)=lower(?) LIMIT 1",(name,)).fetchone()
        if r:return r["id"]
    return None

def import_db(path,source):
    sch=detect(path)
    if not sch["show_table"]: raise ValueError("No recognizable SickChill show table found. Tables: "+", ".join(sch["tables"]))
    stat=dict(shows_found=0,shows_imported=0,shows_skipped=0,episodes_found=0,episodes_imported=0,episodes_skipped=0)
    src,dst=cx(path),cx(); mapping={}
    try:
        rows=src.execute(f'SELECT * FROM "{sch["show_table"]}"').fetchall(); stat["shows_found"]=len(rows)
        for r in rows:
            legacy=i(pick(r,"indexer_id","tvdb_id","show_id")); tvdb=i(pick(r,"tvdb_id","indexer_id"))
            imdb=s(pick(r,"imdb_id","imdbid")); name=s(pick(r,"show_name","name","showname")) or "Unknown"
            if imdb and not imdb.startswith("tt"):
                try: imdb=f"tt{int(imdb):07d}"
                except: pass
            nid=existing(dst,imdb=imdb,tvdb=tvdb,legacy=legacy,name=name)
            if nid: stat["shows_skipped"]+=1
            else:
                cur=dst.execute("""INSERT INTO shows(imdb_id,tvdb_id,legacy_indexer_id,name,first_air_date,location,network,genre,quality,paused,anime,status,legacy_data)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (imdb,tvdb,legacy,name,s(pick(r,"startyear","first_air_date")),s(pick(r,"location","path")),
                   s(pick(r,"network")),s(pick(r,"genre")),s(pick(r,"quality")),i(pick(r,"paused")) or 0,
                   i(pick(r,"anime")) or 0,"Paused" if (i(pick(r,"paused")) or 0) else "Active",json.dumps(dict(r),default=str)))
                nid=cur.lastrowid; stat["shows_imported"]+=1
            if legacy is not None:mapping[legacy]=nid
        if sch["episode_table"]:
            eps=src.execute(f'SELECT * FROM "{sch["episode_table"]}"').fetchall(); stat["episodes_found"]=len(eps)
            for r in eps:
                lid=i(pick(r,"showid","show_id","indexer_id","tvdb_id")); sid=mapping.get(lid) or (existing(dst,tvdb=lid,legacy=lid) if lid is not None else None)
                sea,ep=i(pick(r,"season")),i(pick(r,"episode"))
                if not sid or sea is None or ep is None: stat["episodes_skipped"]+=1; continue
                try:
                    dst.execute("""INSERT INTO episodes(show_id,season,episode,name,airdate,status,location,file_size,release_name,quality,legacy_data)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                      (sid,sea,ep,s(pick(r,"name")),s(pick(r,"airdate")),s(pick(r,"status")),s(pick(r,"location")),
                       i(pick(r,"file_size","filesize")),s(pick(r,"release_name","release")),s(pick(r,"quality")),json.dumps(dict(r),default=str)))
                    stat["episodes_imported"]+=1
                except sqlite3.IntegrityError: stat["episodes_skipped"]+=1
        dst.execute("""INSERT INTO import_runs(source_name,shows_found,shows_imported,shows_skipped,episodes_found,episodes_imported,episodes_skipped)
                     VALUES(?,?,?,?,?,?,?)""",(source,stat["shows_found"],stat["shows_imported"],stat["shows_skipped"],stat["episodes_found"],stat["episodes_imported"],stat["episodes_skipped"]))
        dst.commit()
    finally: src.close(); dst.close()
    stat["schema"]=sch; return stat


SECRET_WORDS=("password","passwd","apikey","api_key","token","secret","cookie","username","user_key","passkey")

def is_secret_name(name):
    n=name.lower()
    return any(w in n for w in SECRET_WORDS)

def parse_sickchill_config(path):
    cfg=configparser.ConfigParser(interpolation=None,strict=False)
    cfg.optionxform=str
    cfg.read(path,encoding="utf-8")
    summary={"sections":0,"settings":0,"secret_settings":0,"mapped":{}}
    with cx() as c:
        for sec in cfg.sections():
            summary["sections"]+=1
            for name,value in cfg[sec].items():
                secret=1 if is_secret_name(name) else 0
                summary["settings"]+=1
                summary["secret_settings"]+=secret
                c.execute("""INSERT INTO settings(section,name,value,is_secret,source,updated_at)
                             VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
                             ON CONFLICT(section,name) DO UPDATE SET
                             value=excluded.value,is_secret=excluded.is_secret,
                             source=excluded.source,updated_at=CURRENT_TIMESTAMP""",
                          (sec,name,value,secret,"sickchill"))
        c.commit()
    g=dict(cfg["General"]) if cfg.has_section("General") else {}
    summary["mapped"]={
        "search":{"use_nzbs":g.get("use_nzbs"),"use_torrents":g.get("use_torrents"),
                  "dailysearch_frequency":g.get("dailysearch_frequency"),
                  "backlog_frequency":g.get("backlog_frequency"),
                  "backlog_days":g.get("backlog_days")},
        "downloaders":{"nzb_method":g.get("nzb_method"),"torrent_method":g.get("torrent_method")},
        "postprocessing":{"tv_download_dir":g.get("tv_download_dir"),
                          "process_method":g.get("process_method"),
                          "process_automatically":g.get("process_automatically"),
                          "rename_episodes":g.get("rename_episodes")},
        "library":{"root_dirs":g.get("root_dirs")},
        "naming":{"naming_pattern":g.get("naming_pattern")},
        "metadata":{"metadata_kodi":g.get("metadata_kodi")}
    }
    return summary

def get_settings_grouped():
    with cx() as c:
        rows=c.execute("SELECT section,name,value,is_secret,source FROM settings ORDER BY section,name").fetchall()
    grouped={}
    for r in rows:
        grouped.setdefault(r["section"],[]).append({
            "name":r["name"],
            "value":"••••••••" if r["is_secret"] and r["value"] else r["value"],
            "is_secret":bool(r["is_secret"]),
            "source":r["source"]
        })
    return grouped

def tmdb(path,params=None):
    # Shared metadata client supports both TMDB_BEARER_TOKEN and TMDB_API_KEY,
    # and can also fall back to imported SickChill settings.
    return tmdb_client.get(path, params=params or {}, db_path=DB, timeout=20)

def metadata_error_response(ex, status=500):
    if isinstance(ex, tmdb_client.TMDBConfigurationError):
        return jsonify(error=str(ex), code="tmdb_not_configured", tmdb=tmdb_client.configured(DB)), 400
    if isinstance(ex, tmdb_client.TMDBUnauthorizedError):
        return jsonify(error=str(ex), code="tmdb_unauthorized", tmdb=tmdb_client.configured(DB)), 401
    if isinstance(ex, tmdb_client.TMDBRequestError):
        return jsonify(error=str(ex), code="tmdb_request_failed", tmdb=tmdb_client.configured(DB)), 502
    return jsonify(error=str(ex)), status

@app.errorhandler(Exception)
def api_exception_json(ex):
    if request.path.startswith("/api/"):
        code = getattr(ex, "code", 500)
        try:
            code = int(code)
        except Exception:
            code = 500
        if code < 400:
            code = 500
        return jsonify(error=str(ex), endpoint=request.path), code
    raise ex


PUBLIC_PATHS={"/login","/about","/about/","/version","/routes","/api/routes","/library-health","/library-health/","/library_health","/health/library","/api/about","/api/about/","/api/version","/api/version/","/api/health","/api/security/status","/database-safety","/database-safety/","/api/protection/status","/api/protection/backups"}

@app.before_request
def enforce_security():
    g.api_identity=None
    path=request.path
    if path.startswith("/static/"):
        return None

    # Existing integration tokens remain valid and do not require browser CSRF.
    auth=request.headers.get("Authorization","")
    if auth.lower().startswith("bearer "):
        ident=release.verify_api_token(auth.split(None,1)[1].strip())
        if ident:
            g.api_identity=ident
            return None
        if path.startswith("/api/"):
            return jsonify(error="Invalid API token"),401

    if path in PUBLIC_PATHS:
        return None

    remote=request.remote_addr or ""
    if path=="/security/setup" and not security.admin_configured():
        if security.is_loopback(remote):
            return None
        return jsonify(error="Administrator setup is only available from the TV Manager PC."),403

    enabled=security.browser_auth_enabled()

    # Local-first compatibility: localhost remains open until the user explicitly
    # enables browser authentication. Remote clients are never allowed this bypass.
    if not enabled:
        if security.is_loopback(remote):
            return None
        return jsonify(error="Remote/LAN access is blocked until browser authentication is configured and enabled."),403

    if not session.get("admin_user"):
        if path.startswith("/api/"):
            return jsonify(error="Authentication required"),401
        return redirect(url_for("login",next=request.full_path if request.query_string else request.path))

    if request.method in {"POST","PUT","PATCH","DELETE"}:
        expected=session.get("csrf_token")
        supplied=request.headers.get("X-CSRF-Token","")
        if not expected or not supplied or not __import__("hmac").compare_digest(expected,supplied):
            security.event("csrf_rejected",session.get("admin_user"),remote,path)
            return jsonify(error="CSRF validation failed"),403
    return None

@app.after_request
def security_headers(response):
    if getattr(g,"api_identity",None):
        release.log_api_access(g.api_identity.get("id"),request.method,request.path,request.remote_addr,response.status_code)
    response.headers.setdefault("X-Content-Type-Options","nosniff")
    response.headers.setdefault("X-Frame-Options","SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy","same-origin")
    response.headers.setdefault("Permissions-Policy","camera=(), microphone=(), geolocation=()")
    if session.get("admin_user"):
        token=security.csrf_value(session)
        response.set_cookie("tvmanager_csrf",token,httponly=False,samesite="Lax",
                            secure=app.config["SESSION_COOKIE_SECURE"])
    return response

@app.route("/login",methods=["GET","POST"])
def login():
    if not security.admin_configured():
        return redirect(url_for("security_setup"))
    error=None
    if request.method=="POST":
        user,error=security.authenticate(request.form.get("username"),request.form.get("password"),request.remote_addr)
        if user:
            session.clear()
            session["admin_user"]=user["username"]
            security.csrf_value(session)
            target=request.args.get("next") or "/dashboard"
            if not target.startswith("/") or target.startswith("//"):
                target="/dashboard"
            return redirect(target)
    return render_template("login.html",error=error)

@app.post("/logout")
def logout():
    username=session.get("admin_user")
    session.clear()
    security.event("logout",username,request.remote_addr,"Browser logout")
    return redirect(url_for("login"))

@app.route("/security/setup",methods=["GET","POST"])
def security_setup():
    if not security.is_loopback(request.remote_addr):
        return jsonify(error="Administrator setup is only available from the TV Manager PC."),403
    error=None;message=None
    configured=security.admin_configured()
    if configured:
        if not session.get("admin_user"):
            return redirect(url_for("login"))
        return redirect("/settings")
    if request.method=="POST":
        try:
            username=security.set_admin_password(request.form.get("username","admin"),request.form.get("password",""))
            security.set_browser_auth(True)
            session.clear();session["admin_user"]=username;security.csrf_value(session)
            return redirect("/settings")
        except Exception as ex:
            error=str(ex)
    return render_template("security_setup.html",configured=configured,error=error,message=message)

@app.get("/api/security/status")
def api_security_status():
    st=security.status()
    local=security.is_loopback(request.remote_addr)
    if not (session.get("admin_user") or local):
        st["admin"]=None
    return jsonify(**st,remote_addr=request.remote_addr if local else None,is_loopback=local)

@app.post("/api/security/password")
def api_security_password():
    if security.admin_configured() and not session.get("admin_user"):
        return jsonify(error="Authentication required"),401
    if not security.is_loopback(request.remote_addr) and not session.get("admin_user"):
        return jsonify(error="Password setup requires local access"),403
    body=request.get_json(silent=True) or {}
    try:
        username=security.set_admin_password(body.get("username","admin"),body.get("password",""))
        return jsonify(ok=True,username=username)
    except Exception as ex:
        return jsonify(error=str(ex)),400

@app.post("/api/security/browser-auth")
def api_security_browser_auth():
    body=request.get_json(silent=True) or {}
    try:
        security.set_browser_auth(bool(body.get("enabled")))
        return jsonify(ok=True,**security.status())
    except Exception as ex:
        return jsonify(error=str(ex)),400

@app.get("/api/security/events")
def api_security_events():
    return jsonify(results=security.recent_events(100))

@app.get("/")
def home(): return render_template("index.html")

@app.get("/trakt")
def trakt_discover_page():
    return render_template("trakt.html")

@app.get("/show-queue")
def show_queue_page():
    return render_template("show_queue.html")

@app.get("/api/trakt/status")
def api_trakt_status():
    return jsonify(trakt_client.status())

@app.post("/api/trakt/settings")
def api_trakt_settings():
    body=request.get_json(silent=True) or {}
    client_id=(body.get("client_id") or body.get("api_key") or "").strip()
    access_token=(body.get("access_token") or "").strip()
    if client_id:
        engine.set_setting("Trakt","client_id",client_id,is_secret=1,source="tvmanager")
    if access_token:
        engine.set_setting("Trakt","access_token",access_token,is_secret=1,source="tvmanager")
    return jsonify(ok=True, status=trakt_client.status())

@app.get("/api/trakt/shows")
def api_trakt_shows():
    category=(request.args.get("category") or "trending").strip().lower()
    query=(request.args.get("q") or "").strip()
    limit=int(request.args.get("limit") or 50)
    page=int(request.args.get("page") or 1)
    try:
        rows=trakt_client.search_shows(query,limit) if query else trakt_client.discover(category,page,limit)
        with cx() as c:
            existing={
                (r["trakt_id"], r["imdb_id"], r["tmdb_id"], r["tvdb_id"])
                for r in c.execute("SELECT trakt_id, imdb_id, tmdb_id, tvdb_id FROM shows").fetchall()
            }
        for row in rows:
            row["saved"] = any(
                (row.get("trakt_id") and row.get("trakt_id")==e[0]) or
                (row.get("imdb_id") and row.get("imdb_id")==e[1]) or
                (row.get("tmdb_id") and row.get("tmdb_id")==e[2]) or
                (row.get("tvdb_id") and row.get("tvdb_id")==e[3])
                for e in existing
            )
        return jsonify(ok=True,results=rows,count=len(rows),category=category,page=page,limit=limit,status=trakt_client.status())
    except Exception as e:
        return jsonify(error=str(e),status=trakt_client.status()),400

@app.post("/api/trakt/add-show")
def api_trakt_add_show():
    body=request.get_json(silent=True) or {}
    name=(body.get("name") or body.get("title") or "").strip()
    if not name:
        return jsonify(error="Trakt show payload is missing a show name."),400
    try:
        location=requested_show_destination(body,name)
    except ValueError as exc:
        return jsonify(error=str(exc)),400
    trakt_id=body.get("trakt_id")
    trakt_slug=body.get("trakt_slug")
    imdb_id=body.get("imdb_id")
    tmdb_id=body.get("tmdb_id")
    tvdb_id=body.get("tvdb_id")
    with cx() as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            __import__("show_preferences").options(body)
            location=requested_show_destination(body,name,c)
        except ValueError as exc: return jsonify(error=str(exc)),400
        found=c.execute("""SELECT id,name FROM shows WHERE
            (? IS NOT NULL AND trakt_id=?) OR
            (? IS NOT NULL AND imdb_id=?) OR
            (? IS NOT NULL AND tmdb_id=?) OR
            (? IS NOT NULL AND tvdb_id=?) OR
            lower(name)=lower(?)
            LIMIT 1""",(trakt_id,trakt_id,imdb_id,imdb_id,tmdb_id,tmdb_id,tvdb_id,tvdb_id,name)).fetchone()
        if found:
            return jsonify(ok=True,created=False,show_id=found["id"],message=f"{found['name']} is already in TV Manager.")
        c.execute("""INSERT INTO shows(trakt_id,trakt_slug,tmdb_id,imdb_id,tvdb_id,name,original_name,first_air_date,overview,network,status,quality,monitor_new,search_enabled,added_at,location,season_folders)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (trakt_id,trakt_slug,tmdb_id,imdb_id,tvdb_id,name,body.get("original_name") or name,
             body.get("first_air_date") or body.get("first_aired"),body.get("overview") or "",
             body.get("network") or "", "Wanted", body.get("quality") or "HD", 1, 1, datetime.now().isoformat(timespec="seconds"),location,1))
        sid=c.execute("SELECT last_insert_rowid()").fetchone()[0]
        try: __import__("show_preferences").apply(c,sid,{**__import__("show_preferences").defaults(c),**body})
        except ValueError as exc:
            c.rollback();return jsonify(error=str(exc)),400
        c.commit()
    return jsonify(ok=True,created=True,show_id=sid,message=f"{name} added from Trakt.tv.")


def _normalize_queue_airdate(value):
    """Normalize legacy SickChill/imported airdate values to YYYY-MM-DD for API clients.

    Some SickChill/imported rows store dates as Python ordinals (for example
    737203) instead of normal ISO text.  Those values looked like IDs in the
    Show Queue screenshot, so normalize them before returning rows to the UI.
    Unknown numeric fragments such as ``1`` are not useful dates and are hidden.
    """
    if value is None:
        return ""
    text=str(value).strip()
    if not text or text in {"0","0000-00-00","None","null"}:
        return ""
    # Already ISO-ish
    try:
        if len(text) >= 10 and text[4] == '-' and text[7] == '-':
            return datetime.fromisoformat(text[:10]).date().isoformat()
    except Exception:
        pass
    # Common US imported values
    for fmt in ("%m/%d/%Y","%m-%d-%Y","%Y%m%d","%Y/%m/%d","%d-%b-%Y","%b %d, %Y"):
        try:
            return datetime.strptime(text[:20],fmt).date().isoformat()
        except Exception:
            pass
    # SickChill/Python ordinal dates occasionally appear in imported data.
    try:
        if text.isdigit() and 700000 <= int(text) <= 900000:
            return datetime.fromordinal(int(text)).date().isoformat()
    except Exception:
        pass
    # Unix timestamps occasionally appear in legacy data.
    try:
        if text.isdigit() and len(text) in (10,13):
            ts=int(text[:10])
            if ts > 0:
                return datetime.fromtimestamp(ts).date().isoformat()
    except Exception:
        pass
    # Small numeric fragments are not real dates; hide instead of showing noise.
    if text.isdigit():
        return ""
    return text

def _queue_download_percent(row):
    total=int(row.get("episode_count") or 0)
    downloaded=int(row.get("downloaded_count") or 0)
    return round((downloaded / total) * 100, 4) if total else 0

def _ignore_season_zero_counts():
    return engine.as_bool(engine.get_setting("TVManager", "ignore_season_zero_counts", "1"), True)

def _queue_episode_filter(alias="e", ignore_specials=None, include_ignored=False):
    if ignore_specials is None:
        ignore_specials = _ignore_season_zero_counts()
    return episode_rules.considered_sql(alias, include_ignored=include_ignored, ignore_specials=ignore_specials)

def _format_episode_code(season, episode):
    try:
        return f"S{int(season):02d}E{int(episode):02d}"
    except Exception:
        return ""

def _queue_missing_display(row, limit=12):
    raw = row.get("missing_episode_numbers") or ""
    parts = [x for x in str(raw).split(",") if x]
    if not parts:
        return "Complete" if int(row.get("missing_count") or 0) == 0 else ""
    shown = parts[:limit]
    more = len(parts) - len(shown)
    return ", ".join(shown) + (f" +{more} more" if more > 0 else "")

def _queue_status_rank(status):
    return {"Wanted": 1, "Upcoming": 2, "Continuing": 3, "Active": 3, "Paused": 4, "Ended": 5}.get(str(status or ""), 99)

def _queue_quality_rank(quality):
    text=str(quality or "").upper()
    order=["SD", "HD", "720", "720P", "1080", "1080P", "4K", "UHD", "2160", "2160P"]
    for idx, marker in enumerate(order):
        if marker in text:
            return idx
    return 99

def _sort_show_queue_rows(rows, sort, direction):
    reverse = str(direction).lower() == "desc"
    def date_key(v):
        value = _normalize_queue_airdate(v)
        return value or "9999-12-31"
    def key(row):
        name=str(row.get("name") or "").casefold()
        if sort in {"downloads", "downloaded", "missing_downloads"}:
            # v18.1: SickChill-style queue priority.  Shows needing attention
            # sort by missing episode count first, then by downloaded/total counts.
            return (int(row.get("missing_count") or 0), int(row.get("downloaded_count") or 0), int(row.get("episode_count") or 0), _queue_download_percent(row), name)
        if sort in {"download_percent", "percent", "complete"}:
            return (_queue_download_percent(row), int(row.get("downloaded_count") or 0), int(row.get("episode_count") or 0), name)
        if sort in {"missing", "wanted_missing"}:
            return (int(row.get("missing_count") or 0), int(row.get("downloaded_count") or 0), int(row.get("episode_count") or 0), name)
        if sort == "size":
            return (int(row.get("size_bytes") or 0), name)
        if sort == "next":
            return (date_key(row.get("next_ep")), name)
        if sort == "prev":
            return (date_key(row.get("prev_ep")), name)
        if sort == "network":
            return (str(row.get("network") or "").casefold(), name)
        if sort == "quality":
            return (_queue_quality_rank(row.get("quality")), str(row.get("quality") or "").casefold(), name)
        if sort == "active":
            return (int(row.get("active_flag") or 0), name)
        if sort == "status":
            return (_queue_status_rank(row.get("status")), str(row.get("status") or "").casefold(), name)
        return (name,)
    return sorted(rows, key=key, reverse=reverse)

@app.get("/api/show-queue")
def api_show_queue():
    q=(request.args.get("q") or "").strip()
    status=(request.args.get("status") or "").strip()
    active=(request.args.get("active") or "").strip().lower()
    sort=(request.args.get("sort") or "show").strip().lower()
    direction=(request.args.get("direction") or "asc").strip().lower()
    try: limit=max(1,min(int(request.args.get("limit") or 100),250))
    except Exception: limit=100
    try: offset=max(0,int(request.args.get("offset") or 0))
    except Exception: offset=0
    ignore_specials = _ignore_season_zero_counts()
    episode_filter = _queue_episode_filter("e", ignore_specials)
    where=[]; params=[]
    if q:
        like=f"%{q}%"; where.append("(s.name LIKE ? COLLATE NOCASE OR COALESCE(s.network,'') LIKE ? COLLATE NOCASE OR COALESCE(s.imdb_id,'') LIKE ? COLLATE NOCASE OR COALESCE(s.location,'') LIKE ? COLLATE NOCASE)"); params.extend([like]*4)
    if status:
        where.append("COALESCE(s.status,'')=?"); params.append(status)
    if active in {"yes","true","1"}:
        where.append("COALESCE(s.paused,0)=0 AND COALESCE(s.search_enabled,1)=1")
    elif active in {"no","false","0"}:
        where.append("(COALESCE(s.paused,0)=1 OR COALESCE(s.search_enabled,1)=0)")
    where_sql=(" WHERE "+" AND ".join(where)) if where else ""
    # v17.23.0: sort in Python after fetching the filtered set so display values
    # like 3/7 never drive ordering. Downloads is sorted by real downloaded count,
    # then total episode count and completion percent. Legacy ordinal dates are
    # normalized before date sorting and display.
    sql=f"""SELECT s.id, s.name, s.network, COALESCE(s.quality,'HD') quality, COALESCE(s.status,'Wanted') status,
              s.paused, s.search_enabled, s.monitor_new,
              (CASE WHEN COALESCE(s.paused,0)=0 AND COALESCE(s.search_enabled,1)=1 THEN 1 ELSE 0 END) active_flag,
              (SELECT MIN(e.airdate) FROM episodes e WHERE e.show_id=s.id AND e.airdate>=date('now') {episode_filter}) next_ep,
              (SELECT MAX(e.airdate) FROM episodes e WHERE e.show_id=s.id AND e.airdate<date('now') {episode_filter}) prev_ep,
              (SELECT COUNT(*) FROM episodes e WHERE e.show_id=s.id {episode_filter} AND e.location IS NOT NULL AND TRIM(e.location)<>'') downloaded_count,
              (SELECT COUNT(*) FROM episodes e WHERE e.show_id=s.id {episode_filter}) episode_count,
              (SELECT COUNT(*) FROM episodes e WHERE e.show_id=s.id {episode_filter} AND (e.location IS NULL OR TRIM(e.location)='')) missing_count,
              COALESCE((SELECT GROUP_CONCAT('S' || printf('%02d', e.season) || 'E' || printf('%02d', e.episode), ',')
                        FROM episodes e WHERE e.show_id=s.id {episode_filter}
                        AND (e.location IS NULL OR TRIM(e.location)='')
                        ORDER BY e.season,e.episode), '') missing_episode_numbers,
              COALESCE((SELECT SUM(COALESCE(e.file_size,0)) FROM episodes e WHERE e.show_id=s.id {episode_filter}),0) size_bytes
           FROM shows s{where_sql}"""
    with cx() as c:
        rows=[dict(r) for r in c.execute(sql,params).fetchall()]
    total=len(rows)
    rows=_sort_show_queue_rows(rows, sort, direction)
    page_rows=rows[offset:offset+limit]
    for row in page_rows:
        row["next_ep"]=_normalize_queue_airdate(row.get("next_ep"))
        row["prev_ep"]=_normalize_queue_airdate(row.get("prev_ep"))
        row["download_percent"]=_queue_download_percent(row)
        row["missing_display"]=_queue_missing_display(row)
    return jsonify(results=page_rows,total=total,count=len(page_rows),limit=limit,offset=offset,next_offset=(offset+limit if offset+limit<total else None),has_more=offset+limit<total,sort=sort,direction=direction,ignore_season_zero_counts=ignore_specials)

@app.get("/manager")
def manager(): return render_template("manager.html")

@app.get("/show/<int:sid>")
def show_detail_page(sid):
    return render_template("show_detail.html", show_id=sid)


@app.get("/workflow")
def workflow_page(): return render_template("workflow.html")

@app.get("/launchpad")
def launchpad_page(): return render_template("launchpad.html")

@app.get("/setup")
@app.get("/setup-assistant")
def setup_assistant_page(): return render_template("setup_assistant.html")

@app.get("/api/launchpad/summary")
def api_launchpad_summary():
    try:
        health = library_maintenance.library_health_report(DB, duplicate_limit=10, sample_limit=8)
        health_error = None
    except Exception as exc:
        health = {"counts": {}, "recommendations": [str(exc)]}
        health_error = str(exc)
    payload = operator_experience.launchpad_summary(DB, APP_VERSION, health)
    payload["readiness_label"] = str(payload.get("readiness") or "unknown").replace("_", " ").title()
    payload["readiness_explanation"] = "Replacement readiness is a launchpad score summarizing whether TV Manager has imported shows, library-health blockers, metadata gaps, downloader configuration, and operator actions still needing attention."
    if health_error:
        payload["health_warning"] = health_error
    return jsonify(payload)

@app.get("/api/setup/summary")
def api_setup_summary():
    try:
        health = library_maintenance.library_health_report(DB, duplicate_limit=10, sample_limit=8)
    except Exception as exc:
        health = {"counts": {}, "recommendations": [str(exc)]}
    return jsonify(operator_experience.setup_assistant_summary(DB, BASE, APP_VERSION, health))

@app.get("/api/workflow/summary")
def api_workflow_summary():
    """Operator workflow summary for replacement/cutover readiness."""
    try:
        dashboard_stats = dashboard().get_json() if hasattr(dashboard(), "get_json") else {}
    except Exception:
        dashboard_stats = {}
    try:
        health = library_maintenance.library_health_report(DB, duplicate_limit=10, sample_limit=8)
    except Exception as exc:
        health = {"counts": {}, "recommendations": [f"Library Health needs attention: {exc}"]}
    try:
        verification = _active_import_verification()
    except Exception as exc:
        verification = {"verification_error": str(exc)}
    try:
        with cx() as c:
            latest = c.execute("""SELECT id,source_name,started_at,finished_at,status,shows_imported,episodes_imported
                                  FROM import_runs ORDER BY id DESC LIMIT 1""").fetchone()
            latest_import = dict(latest) if latest else None
            import_runs = c.execute("SELECT COUNT(*) c FROM import_runs").fetchone()["c"]
    except Exception as exc:
        latest_import = None
        import_runs = 0
        verification.setdefault("verification_error", str(exc))
    counts = health.get("counts", {}) or {}
    steps = [
        {"id":"install","label":"Install TV Manager","status":"done","detail":"Application package is running and reporting version " + APP_VERSION},
        {"id":"import","label":"Import SickChill","status":"done" if import_runs else "next","detail":"Import history exists." if import_runs else "Use Import Center to analyze, preview, and import a copied sickbeard.db."},
        {"id":"verify","label":"Validate Library Health","status":"attention" if any(int(counts.get(k,0) or 0) for k in ("missing_files","duplicate_groups","shows_without_location")) else "done", "detail":"Review missing files, duplicate groups, folder paths, and metadata gaps."},
        {"id":"configure","label":"Configure automation","status":"next","detail":"Connect download clients, providers, metadata, subtitles, naming, and notifications."},
        {"id":"cutover","label":"Cut over from SickChill","status":"planned","detail":"Run both side-by-side first, stop SickChill only after imports and health checks are clean."},
    ]
    return jsonify(ok=True, version=APP_VERSION, stats=dashboard_stats, health_counts=counts,
                   recommendations=health.get("recommendations", []), verification=verification,
                   latest_import=latest_import, import_runs=import_runs, steps=steps)

def _render_library_health_fallback(error=None):
    note = "Library Health template fallback rendered." if error else "Library Health route is active."
    err = f'<p class="notice warn">Template/static issue: {str(error)[:160]}</p>' if error else ""
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Library Health - TV Manager</title><link rel="stylesheet" href="/static/style.css"></head><body><main class="shell manager-shell"><header class="topbar"><div><p class="eyebrow">LIBRARY HEALTH</p><h1>Library Health</h1><p class="subtitle">Server-rendered fallback page. Version v{APP_VERSION}</p></div></header><nav class="appnav professional-nav"><a href="/dashboard">Dashboard</a><a href="/manager">Shows</a><a href="/library-health" aria-current="page">Library Health</a><a href="/about">About</a><a href="/system">System</a><a href="/import">Migration</a></nav><section class="panel"><h2>Page route verified</h2><p class="notice good">{note}</p>{err}<p>Use <code>/api/library/health-report</code> for the live JSON health report.</p><p><button class="btn" onclick="location.reload()">Reload</button> <a class="btn secondary" href="/api/library/health-report">Open health API</a></p></section><footer class="app-version-footer"><span>TV Manager</span><strong>v{APP_VERSION}</strong><a href="/about">About</a></footer></main></body></html>'''

@app.get("/library-health")
@app.get("/library-health/")
@app.get("/library_health")
@app.get("/health/library")
def library_health_page():
    try:
        return render_template("library_health.html")
    except Exception as ex:
        return _render_library_health_fallback(ex)

@app.get("/import")
def importer(): return render_template("import.html")
def _about_payload():
    return {
        "product": "TV Manager",
        "version": APP_VERSION,
        "build": "v" + APP_VERSION,
        "source": "VERSION",
        "database": "SQLite local-first",
        "runtime": "Python / Flask / Waitress",
        "support_pages": [
            {"label": "System", "path": "/system"},
            {"label": "Library Health", "path": "/library-health"},
            {"label": "Import Center", "path": "/import"},
        ],
    }

@app.get("/about")
@app.get("/about/")
@app.get("/version")
def about_page():
    # Keep this page dependable for support screenshots. It should not depend on
    # client-side JavaScript and it should continue to render even if a template
    # edit is damaged or stale in the browser cache.
    data = _about_payload()
    try:
        return render_template("about.html", about=data)
    except Exception as ex:
        fallback = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>About TV Manager</title><link rel="stylesheet" href="/static/style.css"></head><body><main class="shell manager-shell"><header class="topbar"><div><p class="eyebrow">ABOUT</p><h1>TV Manager</h1><p class="subtitle">Version and support information.</p></div></header><section class="panel about-card"><p class="eyebrow">RUNNING BUILD</p><h2>TV Manager v{version}</h2><div class="detail-grid"><div><span>Product</span><strong>TV Manager</strong></div><div><span>Version</span><strong>v{version}</strong></div><div><span>Runtime</span><strong>Python / Flask / Waitress</strong></div><div><span>Database</span><strong>SQLite local-first</strong></div></div><p class="notice warn">About template fallback rendered: {error}</p></section><footer class="app-version-footer"><span>TV Manager</span><strong>v{version}</strong></footer></main></body></html>'
        return fallback.format(version=APP_VERSION, error=str(ex)[:120])

@app.get("/api/version")
@app.get("/api/version/")
def api_version():
    return jsonify(product="TV Manager", version=APP_VERSION, build="v"+APP_VERSION, source="VERSION")

@app.get("/api/about")
@app.get("/api/about/")
def api_about():
    return jsonify(**_about_payload())

@app.get("/api/build-info")
@app.get("/api/build-info/")
def api_build_info():
    version_file = BASE / "VERSION"
    version_text = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else None
    return jsonify(
        product="TV Manager",
        version=APP_VERSION,
        version_file=str(version_file),
        version_file_exists=version_file.exists(),
        version_file_text=version_text,
        app_file=str(Path(__file__).resolve()),
        base_path=str(BASE),
        cwd=os.getcwd(),
        python_executable=sys.executable,
        timestamp=datetime.now().isoformat(timespec="seconds"),
    )

@app.get("/build-info")
@app.get("/build-info/")
def build_info_page():
    version_file = BASE / "VERSION"
    version_text = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "missing"
    html = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TV Manager Build Info</title><link rel="stylesheet" href="/static/style.css?v={version}"></head><body><main class="shell manager-shell"><header class="topbar"><div><p class="eyebrow">BUILD INFO</p><h1>Runtime Verification</h1><p class="subtitle">This page shows the exact files the running server is using.</p></div></header><section class="panel"><div class="detail-grid"><div><span>Version</span><strong>v{version}</strong></div><div><span>VERSION file text</span><strong>{version_text}</strong></div><div><span>App file</span><strong>{app_file}</strong></div><div><span>Base path</span><strong>{base}</strong></div><div><span>Working directory</span><strong>{cwd}</strong></div><div><span>Python</span><strong>{python}</strong></div></div><p><a class="btn" href="/api/build-info">Open JSON build info</a> <a class="btn secondary" href="/about">About</a></p></section><footer class="app-version-footer"><span>TV Manager</span><strong>v{version}</strong><a href="/about">About</a></footer></main></body></html>"""
    return html.format(version=APP_VERSION, version_text=version_text, app_file=Path(__file__).resolve(), base=BASE, cwd=os.getcwd(), python=sys.executable)

def _route_inventory():
    rows=[]
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        methods=sorted(m for m in rule.methods if m not in {"HEAD","OPTIONS"})
        rows.append({"path": rule.rule, "endpoint": rule.endpoint, "methods": methods})
    return rows

@app.get("/api/routes")
def api_routes():
    routes=_route_inventory()
    required=["/about","/library-health","/api/version","/api/about","/api/library/health-report"]
    present={r["path"] for r in routes}
    return jsonify(product="TV Manager", version=APP_VERSION, required={p:(p in present) for p in required}, routes=routes)

@app.get("/routes")
def routes_page():
    routes=_route_inventory()
    required=["/about","/library-health","/api/version","/api/about","/api/library/health-report"]
    present={r["path"] for r in routes}
    rows="".join("<tr><td><code>{}</code></td><td>{}</td><td>{}</td></tr>".format(r["path"], ",".join(r["methods"]), r["endpoint"]) for r in routes)
    checks="".join("<li>{} <code>{}</code></li>".format("OK" if p in present else "MISSING", p) for p in required)
    html=(
        "<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>TV Manager Routes</title><link rel=\"stylesheet\" href=\"/static/style.css\"></head><body><main class=\"shell manager-shell\">"
        f"<header class=\"topbar\"><div><p class=\"eyebrow\">DIAGNOSTICS</p><h1>Route Diagnostics</h1><p class=\"subtitle\">TV Manager v{APP_VERSION}</p></div></header>"
        "<nav class=\"appnav professional-nav\"><a href=\"/dashboard\">Dashboard</a><a href=\"/library-health\">Library Health</a><a href=\"/about\">About</a><a href=\"/system\">System</a></nav>"
        f"<section class=\"panel\"><h2>Required routes</h2><ul class=\"clean-list\">{checks}</ul></section>"
        f"<section class=\"panel\"><h2>Registered Flask routes</h2><table><thead><tr><th>Path</th><th>Methods</th><th>Endpoint</th></tr></thead><tbody>{rows}</tbody></table></section>"
        f"<footer class=\"app-version-footer\"><span>TV Manager</span><strong>v{APP_VERSION}</strong><a href=\"/about\">About</a></footer></main></body></html>"
    )
    return html

@app.errorhandler(404)
def not_found_page(error):
    path=(request.path or "").rstrip("/") or "/"
    if path in {"/about", "/version"}:
        return about_page()
    if path in {"/library-health", "/library_health", "/health/library"}:
        return _render_library_health_fallback("404 fallback rendered; route diagnostics should be checked.")
    html=(
        "<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Not Found - TV Manager</title><link rel=\"stylesheet\" href=\"/static/style.css\"></head><body><main class=\"shell manager-shell\">"
        f"<header class=\"topbar\"><div><p class=\"eyebrow\">NOT FOUND</p><h1>Page not found</h1><p class=\"subtitle\">TV Manager v{APP_VERSION}</p></div></header>"
        f"<section class=\"panel\"><p>The requested URL <code>{request.path}</code> was not found in this running TV Manager instance.</p>"
        "<p>This usually means the server is still running an older install or was not restarted after the package was copied.</p>"
        "<p><a class=\"btn\" href=\"/routes\">Open Route Diagnostics</a> <a class=\"btn secondary\" href=\"/about\">About</a> <a class=\"btn secondary\" href=\"/library-health\">Library Health</a></p></section>"
        f"<footer class=\"app-version-footer\"><span>TV Manager</span><strong>v{APP_VERSION}</strong><a href=\"/about\">About</a></footer></main></body></html>"
    )
    return html,404

@app.get("/api/search")
def search():
    q=(request.args.get("q") or "").strip()
    if not q:return jsonify(error="Enter a TV show name."),400
    if request.args.get("provider")=="tvdb":
        import tvdb_client
        try:
            out=tvdb_client.search(q,request.args.get("year"),DB)
            with cx(readonly=True) as c:
                for row in out:row['saved']=bool(existing(c,tvdb=row['tvdb_id']))
            return jsonify(results=out,count=len(out))
        except ValueError as exc:return jsonify(error=str(exc)),400
    p={"query":q,"include_adult":"false","language":"en-US","page":1}
    if request.args.get("year"):p["first_air_date_year"]=request.args["year"]
    try:
        data=tmdb("/search/tv",p)
        with cx() as c:
            saved={(r["tmdb_id"],r["imdb_id"]) for r in c.execute("SELECT tmdb_id,imdb_id FROM shows")}
        out=[]
        for x in data.get("results",[])[:20]:
            tid=x.get("id"); iid=None
            try:iid=tmdb(f"/tv/{tid}/external_ids").get("imdb_id")
            except:pass
            pp=x.get("poster_path")
            out.append(dict(tmdb_id=tid,imdb_id=iid,name=x.get("name") or x.get("original_name") or "Unknown",
              original_name=x.get("original_name"),first_air_date=x.get("first_air_date"),overview=x.get("overview") or "",
              poster=("https://image.tmdb.org/t/p/w342"+pp if pp else None),vote_average=x.get("vote_average"),
              saved=any(a==tid or (iid and b==iid) for a,b in saved)))
        return jsonify(results=out,count=len(out))
    except Exception as e:return metadata_error_response(e,500)

@app.get("/api/shows")
def shows():
    """Return shows using server-side paging.

    Large SickChill imports can create tens of thousands of show rows. Older
    builds returned every row in one JSON response, which made the Library view
    appear stuck at "Showing…" while the browser tried to download/render the
    entire library. Keep the legacy response shape, but add total/limit/offset
    metadata and default to a bounded page.
    """
    q=(request.args.get("q") or "").strip()
    status=(request.args.get("status") or "").strip()
    group_id=(request.args.get("group_id") or "").strip()
    sort=(request.args.get("sort") or "name").strip().lower()
    direction=(request.args.get("direction") or "asc").strip().lower()
    try:
        limit=int(request.args.get("limit") or 100)
    except Exception:
        limit=100
    try:
        offset=int(request.args.get("offset") or 0)
    except Exception:
        offset=0
    limit=max(1,min(limit,250))
    offset=max(0,offset)

    params=[]
    where=[]
    if q:
        like=f"%{q}%"
        where.append("""(
            s.name LIKE ? COLLATE NOCASE OR
            COALESCE(s.original_name,'') LIKE ? COLLATE NOCASE OR
            COALESCE(s.imdb_id,'') LIKE ? COLLATE NOCASE OR
            CAST(COALESCE(s.tvdb_id,'') AS TEXT) LIKE ? OR
            CAST(COALESCE(s.tmdb_id,'') AS TEXT) LIKE ? OR
            COALESCE(s.location,'') LIKE ? COLLATE NOCASE
        )""")
        params.extend([like]*6)
    if status:
        where.append("COALESCE(s.status,'')=?")
        params.append(status)
    if group_id:
        where.append("EXISTS(SELECT 1 FROM show_group_members gm WHERE gm.show_id=s.id AND gm.group_id=?)")
        params.append(int(group_id))

    where_sql=(" WHERE " + " AND ".join(where)) if where else ""
    order_map={
        "name":"s.name COLLATE NOCASE",
        "added":"COALESCE(s.added_at,'')",
        "status":"COALESCE(s.status,'') COLLATE NOCASE",
        "network":"COALESCE(s.network,'') COLLATE NOCASE",
    }
    order=order_map.get(sort,"s.name COLLATE NOCASE")
    dir_sql="DESC" if direction=="desc" else "ASC"

    page_sql=f"""SELECT s.*,
                  (SELECT COUNT(*) FROM episodes e WHERE e.show_id=s.id) episode_count,
                  (SELECT COUNT(DISTINCT season) FROM episodes e WHERE e.show_id=s.id) season_count
           FROM shows s{where_sql}
           ORDER BY {order} {dir_sql}, s.id ASC
           LIMIT ? OFFSET ?"""
    count_sql=f"SELECT COUNT(*) FROM shows s{where_sql}"

    with cx() as c:
        total=int(c.execute(count_sql,params).fetchone()[0])
        rows=c.execute(page_sql,params+[limit,offset]).fetchall()
        import_runs=0
        try:
            import_runs=int(c.execute("SELECT COUNT(*) FROM import_runs").fetchone()[0])
        except Exception:
            import_runs=0
    recovery=None
    if total==0 and not q and not status and not group_id and import_runs:
        recovery=import_recovery.recover_shows_from_import_audit(DB)
        if recovery.get("created"):
            with cx() as c:
                total=int(c.execute(count_sql,params).fetchone()[0])
                rows=c.execute(page_sql,params+[limit,offset]).fetchall()
    return jsonify(
        results=[dict(r) for r in rows],
        count=len(rows),
        total=total,
        limit=limit,
        offset=offset,
        next_offset=(offset+limit if offset+limit < total else None),
        has_more=offset+limit < total,
        recovery=recovery,
    )




def _lite_ro_connection():
    """Very short-lived read-only connection for UI first-paint endpoints.

    These endpoints are allowed to return stale/degraded data rather than wait behind
    a long writer. They are used only to get the screen usable fast.
    """
    uri = f"file:{DB.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=0.15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=150")
    return con


def _episode_order_sql(sort, direction):
    sort=(sort or "season_episode").strip().lower()
    direction=(direction or "asc").strip().lower()
    desc = direction == "desc"
    if sort == "season_episode":
        return "season DESC, episode DESC" if desc else "season ASC, episode ASC"
    order_map={
        "episode":"episode",
        "title":"COALESCE(name,'') COLLATE NOCASE",
        "airdate":"COALESCE(airdate,'')",
        "status":"COALESCE(status,'') COLLATE NOCASE",
        "quality":"COALESCE(quality,'') COLLATE NOCASE",
        "file":"COALESCE(location,'') COLLATE NOCASE",
    }
    return order_map.get(sort,"season ASC, episode ASC") + (" DESC" if desc else " ASC")


@app.get("/api/shows/<int:sid>/snapshot")
def api_show_snapshot(sid):
    """Never-hang first-paint show snapshot.

    The normal detail endpoint can be delayed by external SQLite locks or expensive
    counts. This endpoint avoids counts, uses a tiny busy timeout, and returns a
    degraded 200 response instead of leaving the browser waiting.
    """
    try:
        with _lite_ro_connection() as c:
            show=c.execute("SELECT id,name,network,status,quality,poster,overview,location,imdb_id,tmdb_id,tvdb_id,genre,first_air_date FROM shows WHERE id=?",(sid,)).fetchone()
            if not show:
                return jsonify(error="Show not found",show=None,degraded=True),404
            return jsonify(show=dict(show),fast=True,degraded=False)
    except Exception as e:
        return jsonify(show={"id":sid,"name":f"Show #{sid}"},error=str(e),fast=True,degraded=True),200


@app.get("/api/shows/<int:sid>/episodes-lite")
def api_show_episodes_lite(sid):
    """Never-hang first-page episode list.

    Returns only what the table needs, avoids COUNT/GROUP BY, and fails soft with
    actionable JSON instead of keeping the screen stuck on Loading.
    """
    season=request.args.get("season")
    q=(request.args.get("q") or "").strip()
    status=(request.args.get("status") or "").strip()
    sort=(request.args.get("sort") or "season_episode").strip().lower()
    direction=(request.args.get("direction") or "asc").strip().lower()
    try: limit=max(1,min(int(request.args.get("limit") or 50),100))
    except Exception: limit=50
    try: offset=max(0,int(request.args.get("offset") or 0))
    except Exception: offset=0
    where=["show_id=?"]; params=[sid]
    try:
        if season not in (None, ""):
            where.append("season=?"); params.append(int(season))
        if status:
            where.append("COALESCE(status,'')=?"); params.append(status)
        if q:
            like=f"%{q}%"
            where.append("(COALESCE(name,'') LIKE ? COLLATE NOCASE OR COALESCE(location,'') LIKE ? COLLATE NOCASE OR CAST(season AS TEXT) LIKE ? OR CAST(episode AS TEXT) LIKE ?)")
            params.extend([like,like,like,like])
        where_sql=" WHERE "+" AND ".join(where)
        order=_episode_order_sql(sort,direction)
        cols="id,show_id,season,episode,name,airdate,status,location,file_size,quality,subtitle_status,monitored,ignored,ignored_reason,ignored_at,ignored_source,managed_note"
        with _lite_ro_connection() as c:
            fetched=c.execute(f"SELECT {cols} FROM episodes{where_sql} ORDER BY {order}, id ASC LIMIT ? OFFSET ?",params+[limit+1,offset]).fetchall()
        has_more=len(fetched)>limit
        rows=fetched[:limit]
        return jsonify(episodes=[dict(r) for r in rows],count=len(rows),total=None,limit=limit,offset=offset,next_offset=(offset+limit if has_more else None),has_more=has_more,fast=True,degraded=False)
    except Exception as e:
        return jsonify(episodes=[],count=0,total=None,limit=limit,offset=offset,next_offset=None,has_more=False,fast=True,degraded=True,error=str(e)),200

@app.get("/api/shows/<int:sid>/episodes")
def eps(sid):
    season=request.args.get("season")
    q=(request.args.get("q") or "").strip()
    status=(request.args.get("status") or "").strip()
    all_mode=(request.args.get("all") or "").lower() in {"1","true","yes"}
    quick=(request.args.get("quick") or "").lower() in {"1","true","yes"}
    sort=(request.args.get("sort") or "season_episode").strip().lower()
    direction=(request.args.get("direction") or "asc").strip().lower()
    try: limit=max(1,min(int(request.args.get("limit") or 100),500))
    except Exception: limit=100
    try: offset=max(0,int(request.args.get("offset") or 0))
    except Exception: offset=0
    with cx(readonly=True) as c:
        show=c.execute("SELECT * FROM shows WHERE id=?",(sid,)).fetchone()
        if not show:
            return jsonify(error="Show not found"),404
        if season is None and not q and not status and not all_mode:
            rows=c.execute("""
                SELECT season, COUNT(*) AS episode_count,
                       SUM(CASE WHEN location IS NOT NULL AND TRIM(location)<>'' THEN 1 ELSE 0 END) AS with_files,
                       SUM(CASE WHEN COALESCE(ignored,0)=1 OR lower(COALESCE(status,''))='ignored' THEN 1 ELSE 0 END) AS ignored_count,
                       SUM(CASE WHEN COALESCE(ignored,0)=0 AND lower(COALESCE(status,''))<>'ignored' THEN 1 ELSE 0 END) AS considered_count
                FROM episodes
                WHERE show_id=?
                GROUP BY season
                ORDER BY season
            """,(sid,)).fetchall()
            return jsonify(show=dict(show),seasons=[dict(r) for r in rows])
        where=["show_id=?"]; params=[sid]
        if season not in (None, ""):
            where.append("season=?"); params.append(int(season))
        if status:
            where.append("COALESCE(status,'')=?"); params.append(status)
        if q:
            like=f"%{q}%"
            where.append("(COALESCE(name,'') LIKE ? COLLATE NOCASE OR COALESCE(location,'') LIKE ? COLLATE NOCASE OR CAST(season AS TEXT) LIKE ? OR CAST(episode AS TEXT) LIKE ?)")
            params.extend([like,like,like,like])
        where_sql=" WHERE "+" AND ".join(where)
        order_map={
            "season_episode":"season ASC, episode ASC",
            "episode":"episode",
            "title":"COALESCE(name,'') COLLATE NOCASE",
            "airdate":"COALESCE(airdate,'')",
            "status":"COALESCE(status,'') COLLATE NOCASE",
            "quality":"COALESCE(quality,'') COLLATE NOCASE",
            "file":"COALESCE(location,'') COLLATE NOCASE",
        }
        if sort=="season_episode":
            order="season DESC, episode DESC" if direction=="desc" else "season ASC, episode ASC"
        else:
            order=order_map.get(sort,"season ASC, episode ASC") + (" DESC" if direction=="desc" else " ASC")
        # Fast episode-list path: keep the first paint lean. Heavy metadata such as overview/stills/release text is not needed for the table and can make large shows feel stuck.
        cols="id,show_id,season,episode,name,airdate,status,location,file_size,quality,subtitle_status,monitored,ignored,ignored_reason,ignored_at,ignored_source,managed_note" if quick else "id,show_id,season,episode,name,airdate,status,location,file_size,release_name,quality,overview,still_url,subtitle_status,monitored,ignored,ignored_reason,ignored_at,ignored_source,managed_note"
        if quick:
            fetch_limit=limit+1
            fetched=c.execute(f"SELECT {cols} FROM episodes{where_sql} ORDER BY {order}, id ASC LIMIT ? OFFSET ?",params+[fetch_limit,offset]).fetchall()
            has_more=len(fetched)>limit
            rows=fetched[:limit]
            total=None
        else:
            total=int(c.execute(f"SELECT COUNT(*) FROM episodes{where_sql}",params).fetchone()[0])
            rows=c.execute(f"SELECT {cols} FROM episodes{where_sql} ORDER BY {order}, id ASC LIMIT ? OFFSET ?",params+[limit,offset]).fetchall()
            has_more=offset+limit<total
    return jsonify(show=dict(show),season=(int(season) if season not in (None,"") else None),episodes=[dict(r) for r in rows],total=total,count=len(rows),limit=limit,offset=offset,next_offset=(offset+limit if has_more else None),has_more=has_more,quick=quick)

@app.get("/api/shows/<int:sid>/seasons-fast")
def api_show_seasons_fast(sid):
    """Return season choices without full counting so Show Detail can paint immediately.

    The older season summary did GROUP BY counts during first load. On large libraries or
    while a subtitle scan is touching files, that made the page look hung. This endpoint
    intentionally returns distinct seasons first; detailed counts refresh later.
    """
    try:
        with cx(readonly=True) as c:
            show=c.execute("SELECT id,name FROM shows WHERE id=?",(sid,)).fetchone()
            if not show:
                return jsonify(error="Show not found"),404
            rows=c.execute("SELECT DISTINCT season FROM episodes WHERE show_id=? ORDER BY season LIMIT 1000",(sid,)).fetchall()
        return jsonify(show=dict(show),seasons=[{"season": int(r["season"] or 0)} for r in rows],fast=True)
    except Exception as e:
        return jsonify(error=str(e),seasons=[],fast=True),200


@app.get("/api/shows/<int:sid>")
def show_detail(sid):
    fast=(request.args.get("fast") or "").lower() in {"1","true","yes"}
    with cx(readonly=True) as c:
        if fast:
            show=c.execute("SELECT * FROM shows WHERE id=?",(sid,)).fetchone()
        else:
            show=c.execute("""
                SELECT s.*,
                       (SELECT COUNT(*) FROM episodes e WHERE e.show_id=s.id) AS episode_count,
                       (SELECT COUNT(*) FROM episodes e WHERE e.show_id=s.id AND COALESCE(e.ignored,0)=0 AND lower(COALESCE(e.status,''))<>'ignored') AS considered_episode_count,
                       (SELECT COUNT(*) FROM episodes e WHERE e.show_id=s.id AND (COALESCE(e.ignored,0)=1 OR lower(COALESCE(e.status,''))='ignored')) AS ignored_episode_count,
                       (SELECT COUNT(DISTINCT season) FROM episodes e WHERE e.show_id=s.id AND COALESCE(e.ignored,0)=0 AND lower(COALESCE(e.status,''))<>'ignored') AS season_count
                FROM shows s WHERE s.id=?
            """,(sid,)).fetchone()
        if not show:
            return jsonify(error="Show not found"),404
    return jsonify(show=dict(show),fast=fast)


def resolve_tmdb_show(show):
    if show["tmdb_id"]:
        return int(show["tmdb_id"])
    if show["imdb_id"]:
        data=tmdb(f'/find/{show["imdb_id"]}',{"external_source":"imdb_id"})
        results=data.get("tv_results") or []
        if results:
            return results[0].get("id")
    if show["tvdb_id"]:
        data=tmdb(f'/find/{show["tvdb_id"]}',{"external_source":"tvdb_id"})
        results=data.get("tv_results") or []
        if results:
            return results[0].get("id")
    return None

@app.post("/api/shows/<int:sid>/refresh/start")
def refresh_show_metadata_start(sid):
    def worker(job_id):
        job_center.update_job(job_id, stage="Show metadata", message="Refreshing show, season and episode metadata.", percent=10, total=1)
        result=metadata_service.refresh_show(sid)
        job_center.update_job(job_id, status="complete", stage="Complete", message="Show metadata refresh complete.", percent=100, result=result, processed=1, succeeded=1)
        return result
    return jsonify(ok=True, job=job_center.run_background("show_metadata_refresh", worker, stage="Queued", message="Show metadata refresh queued.", meta={"show_id":sid}))

@app.post("/api/shows/<int:sid>/refresh")
def refresh_show_metadata(sid):
    with cx() as c:
        show=c.execute("SELECT * FROM shows WHERE id=?",(sid,)).fetchone()
    if not show:
        return jsonify(error="Show not found"),404
    if dict(show).get('metadata_provider')=='tvdb':
        try:return jsonify(ok=True,**metadata_service.refresh_show(sid))
        except ValueError as exc:return jsonify(error=str(exc)),400
    try:
        tmdb_id=resolve_tmdb_show(show)
        if not tmdb_id:
            return jsonify(error="Could not match this imported show to TMDb using its current IMDb/TVDb IDs."),404

        info=tmdb(f"/tv/{tmdb_id}",{"language":dict(show).get("metadata_language") or "en-US","append_to_response":"external_ids"})
        ext=info.get("external_ids") or {}
        poster_path=info.get("poster_path")
        genres=", ".join(x.get("name","") for x in info.get("genres",[]) if x.get("name"))
        networks=", ".join(x.get("name","") for x in info.get("networks",[]) if x.get("name"))

        inserted=0
        updated=0
        with cx() as c:
            c.execute("""UPDATE shows SET
                tmdb_id=?, imdb_id=COALESCE(NULLIF(?,''),imdb_id),
                tvdb_id=COALESCE(?,tvdb_id), name=COALESCE(NULLIF(name_override,''),?), original_name=?,
                first_air_date=?, overview=?, poster=?, vote_average=?,
                network=?, genre=?
                WHERE id=?""",
                (tmdb_id,ext.get("imdb_id"),ext.get("tvdb_id"),
                 info.get("name") or show["name"],info.get("original_name"),
                 info.get("first_air_date"),info.get("overview") or "",
                 ("https://image.tmdb.org/t/p/w500"+poster_path if poster_path else show["poster"]),
                 info.get("vote_average"),networks or show["network"],genres or show["genre"],sid))

            today=date.today().isoformat()
            for season in info.get("seasons",[]):
                sn=season.get("season_number")
                if sn is None:
                    continue
                try:
                    sd=tmdb(f"/tv/{tmdb_id}/season/{sn}",{"language":dict(show).get("metadata_language") or "en-US"})
                except Exception:
                    continue
                for ep in sd.get("episodes",[]):
                    en=ep.get("episode_number")
                    if en is None:
                        continue
                    existing=c.execute("SELECT id,location,status FROM episodes WHERE show_id=? AND season=? AND episode=?",
                                       (sid,sn,en)).fetchone()
                    air=ep.get("air_date")
                    still_path=ep.get("still_path")
                    still_url=("https://image.tmdb.org/t/p/w500"+still_path) if still_path else None
                    default_status=__import__("show_preferences").initial_episode_status(show,air,today)
                    if existing:
                        c.execute("""UPDATE episodes SET
                            name=COALESCE(NULLIF(?,''),name),
                            airdate=COALESCE(NULLIF(?,''),airdate),
                            overview=COALESCE(NULLIF(?,''),overview),
                            still_url=COALESCE(NULLIF(?,''),still_url),
                            tmdb_episode_id=COALESCE(?,tmdb_episode_id),
                            metadata_updated_at=CURRENT_TIMESTAMP
                            WHERE id=?""",(ep.get("name"),air,ep.get("overview") or "",still_url,ep.get("id"),existing["id"]))
                        updated+=1
                    else:
                        c.execute("""INSERT INTO episodes(show_id,season,episode,name,airdate,status,overview,still_url,tmdb_episode_id,metadata_updated_at)
                                     VALUES(?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",(sid,sn,en,ep.get("name"),air,default_status,ep.get("overview") or "",still_url,ep.get("id")))
                        inserted+=1
            c.commit()
        return jsonify(ok=True,tmdb_id=tmdb_id,episodes_inserted=inserted,episodes_updated=updated,
                       message=f"Metadata refreshed. {inserted} episodes added and {updated} existing episodes updated.")
    except Exception as e:
        return metadata_error_response(e,500)

@app.get("/api/dashboard")
def dashboard():
    with cx() as c:
        shows=c.execute("SELECT COUNT(*) c FROM shows").fetchone()["c"]
        episodes=c.execute("SELECT COUNT(*) c FROM episodes").fetchone()["c"]
        downloaded=c.execute("SELECT COUNT(*) c FROM episodes WHERE location IS NOT NULL AND TRIM(location)<>''").fetchone()["c"]
        wanted_sql="""SELECT COUNT(*) c FROM episodes
                            WHERE (location IS NULL OR TRIM(location)='')
                              AND lower(COALESCE(status,'')) IN ('wanted','failed')
                              AND COALESCE(ignored,0)=0 AND lower(COALESCE(status,''))<>'ignored'"""
        if _ignore_season_zero_counts():
            wanted_sql += " AND COALESCE(season,-1)<>0"
        wanted=c.execute(wanted_sql).fetchone()["c"]
    return jsonify(shows=shows,episodes=episodes,downloaded=downloaded,wanted=wanted)


from library_destinations import library_roots, show_destination, rebase_episode_location

@app.get("/library-storage")
def library_storage_page():
    return render_template("library_storage.html")

@app.get("/api/library/storage")
def api_library_storage():
    import library_storage
    roots,_=library_roots(engine.get_setting("General","root_dirs",""))
    return jsonify(results=library_storage.storage_status(roots,ops.map_path),cache_seconds=60)

@app.get("/api/library/locations")
def api_library_locations():
    import library_locations
    with cx() as c:
        return jsonify(results=library_locations.locations(c))

@app.post("/api/library/locations")
def api_library_locations_change():
    import library_locations
    body=request.get_json(silent=True) or {}
    with cx() as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            results=library_locations.change(c,body)
        except library_locations.LocationInUse as exc:
            return jsonify(error=str(exc),shows=exc.shows),409
        except ValueError as exc:
            return jsonify(error=str(exc)),400
    return jsonify(ok=True,results=results)

@app.get("/api/library/destinations")
def api_library_destinations():
    roots, default=library_roots(engine.get_setting("General","root_dirs",""))
    return jsonify(roots=roots, default=default)

def requested_show_destination(body, name, connection=None):
    if connection is None:
        raw=engine.get_setting("General","root_dirs","")
    else:
        row=connection.execute("SELECT value FROM settings WHERE lower(section)='general' AND lower(name)='root_dirs'").fetchone()
        raw=row["value"] if row else ""
    return show_destination(raw,body.get("library_root"),body.get("folder_name") or name)

@app.post("/api/library/destination-preview")
def api_library_destination_preview():
    body=request.get_json(silent=True) or {}
    try:
        return jsonify(location=requested_show_destination(body, body.get("name") or ""))
    except ValueError as exc:
        return jsonify(error=str(exc)),400

@app.patch("/api/shows/<int:sid>/destination")
def api_show_destination(sid):
    body=request.get_json(silent=True) or {}
    with cx() as c:
        c.execute("BEGIN IMMEDIATE")
        show=c.execute("SELECT name,location FROM shows WHERE id=?",(sid,)).fetchone()
        if not show: return jsonify(error="Show not found"),404
        if "previous_location" not in body or (body.get("previous_location") or "") != (show["location"] or ""):
            return jsonify(error="The library folder has changed. Refresh the show and try again."),409
        try:
            location=requested_show_destination(body,show["name"],c)
        except ValueError as exc:
            return jsonify(error=str(exc)),400
        updated=0
        if body.get("update_episode_paths") is True:
            for ep in c.execute("SELECT id,location FROM episodes WHERE show_id=?",(sid,)).fetchall():
                target=rebase_episode_location(ep["location"],show["location"],location)
                if target != ep["location"]:
                    c.execute("UPDATE episodes SET location=? WHERE id=?",(target,ep["id"]))
                    updated+=1
        c.execute("UPDATE shows SET location=? WHERE id=?",(location,sid))
    return jsonify(ok=True,location=location,episode_paths_updated=updated)

@app.post("/api/shows")
def add():
    x=request.get_json() or {}; name=(x.get("name") or "").strip()
    try:
        location=requested_show_destination(x,name)
    except ValueError as exc:
        return jsonify(error=str(exc)),400
    with cx() as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            if x.get('episode_order','official') not in {'official','dvd'}:raise ValueError('Unknown episode order')
            if x.get('episode_order')=='dvd' and x.get('metadata_provider')!='tvdb':raise ValueError('DVD order requires TVDB')
            if x.get('metadata_provider','tmdb') not in {'tmdb','tvdb'}:raise ValueError('Unknown metadata provider')
            if x.get('metadata_provider')=='tvdb' and not str(x.get('tvdb_id','')).isdigit():raise ValueError('A TVDB ID is required')
            __import__("show_preferences").options(x)
            location=requested_show_destination(x,name,c)
        except ValueError as exc: return jsonify(error=str(exc)),400
        if existing(c,tmdb=x.get("tmdb_id"),imdb=x.get("imdb_id"),tvdb=x.get("tvdb_id"),name=name):return jsonify(ok=True,message=f"{name} is already in TV Manager.")
        c.execute("""INSERT INTO shows(tmdb_id,imdb_id,name,original_name,first_air_date,overview,poster,vote_average,status,location,season_folders)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(x.get("tmdb_id"),x.get("imdb_id"),name,x.get("original_name"),x.get("first_air_date"),x.get("overview"),x.get("poster"),x.get("vote_average"),"Wanted",location,1))
        sid=c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.execute('UPDATE shows SET metadata_provider=?,tvdb_id=?,episode_order=? WHERE id=?',(x.get('metadata_provider','tmdb'),x.get('tvdb_id'),x.get('episode_order','official'),sid))
        try: __import__("show_preferences").apply(c,sid,{**__import__("show_preferences").defaults(c),**x})
        except ValueError as exc:
            c.rollback();return jsonify(error=str(exc)),400
    return jsonify(ok=True,show_id=sid,message=f"{name} added to TV Manager."),201

def _save_sickchill_upload():
    f=request.files.get("database")
    if not f or not f.filename:
        return None, None, (jsonify(error="Choose a SickChill database file."),400)
    name=secure_filename(f.filename) or "sickbeard.db"
    dest=IMPORTS/name
    f.save(dest)
    backup=IMPORTS/(name+".backup")
    shutil.copy2(dest,backup)
    return name, dest, None

@app.post("/api/import/sickchill/analyze")
def analyze_sickchill_import():
    name,dest,error=_save_sickchill_upload()
    if error:return error
    try:
        st=sickchill_importer.analyze_database(dest,DB)
        return jsonify(ok=True,source_name=name,**st)
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/import/sickchill/preview")
def preview_sickchill_import():
    name,dest,error=_save_sickchill_upload()
    if error:return error
    try:
        st=sickchill_importer.import_database(dest,DB,name,dry_run=True)
        return jsonify(ok=True,backup=Path(str(dest)+".backup").name,**st)
    except Exception as e:return jsonify(error=str(e)),400

def _set_import_job(job_id: str, **updates):
    with IMPORT_JOBS_LOCK:
        job = IMPORT_JOBS.setdefault(job_id, {})
        job.update(updates)
        job["updated_at"] = datetime.now().isoformat(timespec="seconds")
        return dict(job)

def _get_import_job(job_id: str):
    with IMPORT_JOBS_LOCK:
        job = IMPORT_JOBS.get(job_id)
        return dict(job) if job else None

def _run_sickchill_import_job(job_id: str, source_name: str, dest: Path):
    def progress(event):
        _set_import_job(
            job_id,
            status="running",
            stage=event.get("stage", "running"),
            percent=event.get("percent", 0),
            message=event.get("message", "Import running"),
            counters={
                k: event.get(k) for k in (
                    "shows_found", "shows_processed", "shows_imported", "shows_skipped",
                    "episodes_found", "episodes_processed", "episodes_imported", "episodes_skipped"
                ) if k in event
            },
        )
    try:
        _set_import_job(job_id, status="running", stage="start", percent=1, message="Starting SickChill import", source_name=source_name)
        before=_active_import_verification()
        st=sickchill_importer.import_database(dest,DB,source_name,dry_run=False,progress_callback=progress)
        after=_active_import_verification({"before": before, "importer_visibility": st.get("target_visibility", {})})
        recovery={"attempted": False, "created": 0, "reason": "not needed"}
        if int(after.get("shows") or 0)==0 and (int(st.get("shows_imported") or 0)>0 or int(after.get("imported_show_audit_rows") or 0)>0):
            _set_import_job(job_id, status="running", stage="recover", percent=97, message="Recovering show visibility from import audit trail")
            recovery=import_recovery.recover_shows_from_import_audit(DB)
            after=_active_import_verification({"before": before, "recovery": recovery})
        st["backup"]=Path(str(dest)+".backup").name
        st["active_database_verification"]=after
        _write_import_verification_report({"import_result": st, "verification": after, "recovery": recovery, "job_id": job_id})
        _set_import_job(job_id, status="complete", stage="complete", percent=100, message="Import complete", result=st, counters={
            "shows_imported": st.get("shows_imported",0), "shows_skipped": st.get("shows_skipped",0),
            "episodes_imported": st.get("episodes_imported",0), "episodes_skipped": st.get("episodes_skipped",0),
            "shows_found": st.get("shows_found",0), "episodes_found": st.get("episodes_found",0),
        })
    except Exception as exc:
        _set_import_job(job_id, status="error", stage="error", percent=100, message=str(exc), error=str(exc), traceback=traceback.format_exc(limit=12))

@app.post("/api/import/sickchill/jobs")
@app.post("/api/import/sickchill/jobs/")
def start_sickchill_import_job():
    try:
        name,dest,error=_save_sickchill_upload()
        if error:return error
        job_id=uuid.uuid4().hex
        _set_import_job(job_id, status="queued", stage="queued", percent=0, message="Import queued", source_name=name, created_at=datetime.now().isoformat(timespec="seconds"))
        thread=threading.Thread(target=_run_sickchill_import_job,args=(job_id,name,dest),daemon=True)
        thread.start()
        return jsonify(ok=True,job_id=job_id,status_url=f"/api/import/sickchill/jobs/{job_id}")
    except Exception as exc:
        return jsonify(error=str(exc), endpoint="/api/import/sickchill/jobs"),500

@app.get("/api/import/sickchill/jobs/<job_id>")
@app.get("/api/import/sickchill/jobs/<job_id>/")
def get_sickchill_import_job(job_id):
    job=_get_import_job(job_id)
    if not job:
        return jsonify(error="Import job not found"),404
    return jsonify(ok=True,**job)

@app.post("/api/import/sickchill")
def doimport():
    name,dest,error=_save_sickchill_upload()
    if error:return error
    try:
        before=_active_import_verification()
        st=sickchill_importer.import_database(dest,DB,name,dry_run=False)
        after=_active_import_verification({"before": before, "importer_visibility": st.get("target_visibility", {})})
        recovery={"attempted": False, "created": 0, "reason": "not needed"}
        if int(after.get("shows") or 0)==0 and (int(st.get("shows_imported") or 0)>0 or int(after.get("imported_show_audit_rows") or 0)>0):
            recovery=import_recovery.recover_shows_from_import_audit(DB)
            after=_active_import_verification({"before": before, "recovery": recovery})
        st["backup"]=Path(str(dest)+".backup").name
        st["active_database_verification"]=after
        _write_import_verification_report({"import_result": st, "verification": after, "recovery": recovery})
        return jsonify(ok=True,**st)
    except Exception as e:return jsonify(error=str(e)),400


@app.post("/api/import/config")
def import_config():
    f=request.files.get("config")
    if not f or not f.filename:
        return jsonify(error="Choose a SickChill config.ini file."),400
    name=secure_filename(f.filename) or "config.ini"
    dest=IMPORTS/name
    f.save(dest)
    backup=IMPORTS/(name+".backup")
    shutil.copy2(dest,backup)
    try:
        summary=parse_sickchill_config(dest)
        summary["backup"]=backup.name
        return jsonify(ok=True,**summary)
    except Exception as e:
        return jsonify(error=str(e)),400

@app.get("/api/import/verify")
def api_import_verify():
    recovery={"attempted": False, "created": 0, "reason": "not requested"}
    if request.args.get("recover") in {"1","true","yes"}:
        recovery=import_recovery.recover_shows_from_import_audit(DB)
    data=_active_import_verification({"recovery": recovery})
    _write_import_verification_report(data)
    return jsonify(ok=True, **data)


@app.get("/api/settings")
def settings_api():
    return jsonify(results=get_settings_grouped())




@app.get("/help")
def help_center_page():
    return render_template("help.html", section=None)

@app.get("/help/<slug>")
def help_section_page(slug):
    return render_template("help.html", section=slug)

@app.get("/api/help")
def api_help_index():
    return jsonify(sections=help_content.help_index(), workflows=help_content.WORKFLOW_MAP)

@app.get("/api/help/<slug>")
def api_help_section(slug):
    section=help_content.help_section(slug)
    if not section:
        return jsonify(error="Help section not found"),404
    return jsonify(section={"slug":slug, **section})

@app.get("/api/help/sickchill-parity")
def api_sickchill_parity_help():
    return jsonify(help_content.parity_summary())

@app.get("/api/product/workflow-map")
def api_product_workflow_map():
    return jsonify(workflows=help_content.WORKFLOW_MAP)

@app.get("/dashboard")
def dashboard_page(): return render_template("dashboard.html")

@app.get("/quality")
def quality_page(): return render_template("quality.html")

@app.get("/upcoming")
def upcoming_page(): return render_template("upcoming.html")

@app.get("/missing")
def missing_page(): return render_template("missing.html")

@app.get("/activity")
def activity_page(): return render_template("activity.html")

@app.get("/logs")
def logs_page(): return render_template("logs.html")

@app.get("/download-center")
@app.get("/downloads")
def download_center_page(): return render_template("download_center.html")

@app.get("/manage")
def manage_page(): return render_template("manage.html")

@app.get("/settings")
def settings_page(): return render_template("settings.html")

@app.get("/postprocess")
def postprocess_page(): return render_template("postprocess.html")


@app.get("/api/manage/summary")
def api_manage_summary():
    try:
        sickchill_parity.init(DB)
        return jsonify(ok=True, **sickchill_parity.summary(DB))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.get("/api/manage/backlog-overview")
def api_manage_backlog_overview():
    try:
        sickchill_parity.init(DB)
        return jsonify(ok=True, **sickchill_parity.backlog_overview(DB, request.args.get("limit", 500)))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.post("/api/manage/episode-status/preview")
def api_manage_status_preview():
    try:
        sickchill_parity.init(DB)
        body=request.get_json(silent=True) or {}
        return jsonify(ok=True, **sickchill_parity.status_preview(DB, body))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.post("/api/manage/episode-status/apply")
def api_manage_status_apply():
    try:
        sickchill_parity.init(DB)
        body=request.get_json(silent=True) or {}
        filters=body.get("filters") or body
        new_status=body.get("status") or body.get("new_status")
        monitored=body.get("monitored") if "monitored" in body else None
        def worker(job_id):
            job_center.update_job(job_id, stage="Episode Status Management", message="Applying mass episode status update.", percent=20)
            result=sickchill_parity.status_apply(DB, filters, new_status, monitored)
            engine.log("mass_episode_status", f"Mass episode status update affected {result.get('affected',0)} episodes", data={"filters":filters,"status":new_status,"monitored":monitored})
            job_center.update_job(job_id, status="complete", stage="Complete", message="Episode status update complete.", percent=100, result=result, processed=result.get("affected",0), succeeded=result.get("affected",0))
            return result
        return jsonify(ok=True, job=job_center.run_background("episode_status_management", worker, stage="Queued", message="Episode status update queued.", meta={"filters":filters,"status":new_status}))
    except Exception as e:
        return jsonify(error=str(e)),400


@app.post("/api/episodes/bulk/preview")
def api_episode_bulk_preview():
    try:
        episode_rules.init(DB)
        body=request.get_json(silent=True) or {}
        filters=body.get("filters") or body
        return jsonify(ok=True, **episode_rules.preview(DB, filters))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.post("/api/episodes/bulk/apply/start")
def api_episode_bulk_apply_start():
    try:
        episode_rules.init(DB)
        body=request.get_json(silent=True) or {}
        filters=body.get("filters") or {}
        action=body.get("action") or "bulk_episode_management"
        status=body.get("status") if "status" in body else None
        monitored=body.get("monitored") if "monitored" in body else None
        ignored=body.get("ignored") if "ignored" in body else None
        reason=body.get("reason") or body.get("ignored_reason") or "Bulk episode management"
        note=body.get("note") or ""
        def worker(job_id):
            preview=episode_rules.preview(DB, filters, sample_limit=10)
            job_center.update_job(job_id, stage="Episode Management", message=f"Applying changes to {preview.get('total',0)} episode(s).", percent=25, total=preview.get("total",0))
            result=episode_rules.apply(DB, filters, action, status=status, monitored=monitored, ignored=ignored, reason=reason, note=note)
            engine.log("bulk_episode_management", f"Bulk episode management affected {result.get('affected',0)} episodes", data={"filters":filters,"action":action,"status":status,"monitored":monitored,"ignored":ignored})
            job_center.update_job(job_id, status="complete", stage="Complete", message=result.get("message") or "Episode management complete.", percent=100, result=result, processed=result.get("affected",0), succeeded=result.get("affected",0), total=preview.get("total",0))
            return result
        return jsonify(ok=True, job=job_center.run_background("bulk_episode_management", worker, stage="Queued", message="Episode management queued.", meta={"filters":filters,"action":action}))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.post("/api/shows/<int:sid>/specials/ignore/start")
def api_show_ignore_specials_start(sid):
    def worker(job_id):
        job_center.update_job(job_id, stage="Specials", message="Ignoring Season 00 / Specials for this show.", percent=30)
        result=episode_rules.ignore_specials(DB, sid)
        engine.log("ignore_specials", f"Ignored Season 00 / Specials for show {sid}: {result.get('affected',0)} episode(s)", show_id=sid, data=result)
        job_center.update_job(job_id, status="complete", stage="Complete", message=f"Ignored {result.get('affected',0)} Season 00 episode(s).", percent=100, result=result, processed=result.get("affected",0), succeeded=result.get("affected",0))
        return result
    return jsonify(ok=True, job=job_center.run_background("ignore_show_specials", worker, stage="Queued", message="Ignore Specials queued.", meta={"show_id":sid}))

@app.post("/api/shows/<int:sid>/specials/include/start")
def api_show_include_specials_start(sid):
    def worker(job_id):
        job_center.update_job(job_id, stage="Specials", message="Including Season 00 / Specials for this show.", percent=30)
        result=episode_rules.include_specials(DB, sid)
        engine.log("include_specials", f"Included Season 00 / Specials for show {sid}: {result.get('affected',0)} episode(s)", show_id=sid, data=result)
        job_center.update_job(job_id, status="complete", stage="Complete", message=f"Included {result.get('affected',0)} Season 00 episode(s).", percent=100, result=result, processed=result.get("affected",0), succeeded=result.get("affected",0))
        return result
    return jsonify(ok=True, job=job_center.run_background("include_show_specials", worker, stage="Queued", message="Include Specials queued.", meta={"show_id":sid}))

@app.post("/api/episodes/specials/global-preview")
def api_global_specials_preview():
    try:
        episode_rules.init(DB)
        body=request.get_json(silent=True) or {}
        return jsonify(ok=True, ignore_season_zero_counts=_ignore_season_zero_counts(), **episode_rules.preview(DB, {"specials": True, **body}))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.post("/api/episodes/specials/global-ignore/start")
def api_global_specials_ignore_start():
    def worker(job_id):
        job_center.update_job(job_id, stage="Global Specials", message="Turning on global rule: hide S00/Specials from Missing/Wanted.", percent=10)
        engine.set_setting("TVManager", "ignore_season_zero_counts", "1")
        job_center.update_job(job_id, stage="Global Specials", message="Marking all Season 00 / Specials as ignored and unmonitored.", percent=45)
        result=episode_rules.ignore_specials(DB, None, reason="Season 00 / Specials hidden from Missing/Wanted globally")
        engine.log("global_ignore_specials", f"Globally ignored Season 00 / Specials: {result.get('affected',0)} episode(s)", data=result)
        job_center.update_job(job_id, status="complete", stage="Complete", message=f"S00/Specials are hidden from Missing/Wanted. {result.get('affected',0)} episode(s) updated.", percent=100, result=result, processed=result.get("affected",0), succeeded=result.get("affected",0))
        return result
    return jsonify(ok=True, job=job_center.run_background("global_ignore_specials", worker, stage="Queued", message="Global Specials ignore queued."))

@app.post("/api/episodes/specials/global-include/start")
def api_global_specials_include_start():
    def worker(job_id):
        job_center.update_job(job_id, stage="Global Specials", message="Turning off global S00/Specials hiding rule.", percent=10)
        engine.set_setting("TVManager", "ignore_season_zero_counts", "0")
        job_center.update_job(job_id, stage="Global Specials", message="Returning ignored Season 00 / Specials to considered workflow.", percent=45)
        result=episode_rules.include_specials(DB, None)
        engine.log("global_include_specials", f"Globally included Season 00 / Specials: {result.get('affected',0)} episode(s)", data=result)
        job_center.update_job(job_id, status="complete", stage="Complete", message=f"S00/Specials can appear in Missing/Wanted again. {result.get('affected',0)} episode(s) updated.", percent=100, result=result, processed=result.get("affected",0), succeeded=result.get("affected",0))
        return result
    return jsonify(ok=True, job=job_center.run_background("global_include_specials", worker, stage="Queued", message="Global Specials include queued."))

@app.get("/api/manage/failed-downloads")
def api_manage_failed_downloads():
    try:
        sickchill_parity.init(DB)
        return jsonify(ok=True, **sickchill_parity.failed_downloads(DB, request.args.get("limit",500)))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.post("/api/manage/failed-downloads")
def api_manage_failed_add():
    try:
        sickchill_parity.init(DB)
        body=request.get_json(silent=True) or {}
        result=sickchill_parity.add_failed_download(DB, body.get("title",""), body.get("guid",""), body.get("reason","Manual blacklist"))
        engine.log("failed_release_added", f"Added failed-release blacklist entry: {result.get('title')}", data=result)
        return jsonify(result)
    except Exception as e:
        return jsonify(error=str(e)),400

@app.delete("/api/manage/failed-downloads/<int:failed_id>")
def api_manage_failed_delete(failed_id):
    try:
        sickchill_parity.init(DB)
        return jsonify(sickchill_parity.remove_failed_download(DB, failed_id))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.get("/api/manage/missed-subtitles")
def api_manage_missed_subtitles():
    try:
        sickchill_parity.init(DB)
        return jsonify(ok=True, **sickchill_parity.missed_subtitles(DB, request.args.get("limit",500)))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.get("/api/manage/scene-exceptions")
def api_manage_scene_exceptions():
    try:
        sickchill_parity.init(DB)
        sid=request.args.get("show_id")
        return jsonify(ok=True, **sickchill_parity.scene_exceptions(DB, int(sid) if sid else None))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.post("/api/manage/scene-exceptions")
def api_manage_scene_exception_add():
    try:
        sickchill_parity.init(DB)
        body=request.get_json(silent=True) or {}
        result=sickchill_parity.add_scene_exception(DB, int(body.get("show_id") or 0), body.get("exception_name") or body.get("name") or "", body.get("notes") or "", body.get("source") or "manual")
        engine.log("scene_exception_added", f"Added scene exception: {result.get('exception_name')}", show_id=result.get("show_id"), data=result)
        return jsonify(result)
    except Exception as e:
        return jsonify(error=str(e)),400

@app.delete("/api/manage/scene-exceptions/<int:exception_id>")
def api_manage_scene_exception_delete(exception_id):
    try:
        sickchill_parity.init(DB)
        return jsonify(sickchill_parity.remove_scene_exception(DB, exception_id))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.post("/api/manage/mass-refresh/start")
def api_manage_mass_refresh_start():
    body=request.get_json(silent=True) or {}
    refresh_metadata=bool(body.get("metadata", True))
    refresh_artwork=bool(body.get("artwork", True))
    scan_subtitles=bool(body.get("subtitles", False))
    limit=max(1,min(int(body.get("limit") or 200),2000))
    def worker(job_id):
        steps=max(1, int(refresh_metadata)+int(refresh_artwork)+int(scan_subtitles))
        done=0
        result={"metadata":None,"artwork":None,"subtitles":None}
        if refresh_metadata:
            job_center.update_job(job_id, stage="Metadata", message="Refreshing missing show/episode metadata.", percent=int(done/steps*100), total=steps, processed=done)
            result["metadata"]=metadata_service.refresh_missing_metadata(limit=limit)
            done+=1
        if refresh_artwork:
            job_center.update_job(job_id, stage="Artwork", message="Refreshing show and episode artwork.", percent=int(done/steps*100), total=steps, processed=done)
            result["artwork"]=metadata_service.refresh_artwork(limit=limit, include_episodes=True)
            done+=1
        if scan_subtitles:
            job_center.update_job(job_id, stage="Subtitles", message="Scanning for missing subtitles.", percent=int(done/steps*100), total=steps, processed=done)
            result["subtitles"]=engine.subtitle_scan()
            done+=1
        engine.log("mass_refresh", "SickChill parity mass refresh completed", data=result)
        job_center.update_job(job_id, status="complete", stage="Complete", message="Mass refresh complete.", percent=100, result=result, processed=done, succeeded=done, total=steps)
        return result
    return jsonify(ok=True, job=job_center.run_background("sickchill_mass_refresh", worker, stage="Queued", message="SickChill parity mass refresh queued.", meta={"limit":limit,"metadata":refresh_metadata,"artwork":refresh_artwork,"subtitles":scan_subtitles}))

@app.get("/api/upcoming")
def api_upcoming():
    return jsonify(results=engine.upcoming(max(1,min(90,int(request.args.get("days","14"))))))

@app.get("/api/missing")
def api_missing():
    return jsonify(results=engine.missing(max(1,min(2000,int(request.args.get("limit","500"))))))

@app.get("/api/activity")
def api_activity():
    return jsonify(results=engine.activity(max(1,min(1000,int(request.args.get("limit","200"))))))

@app.get("/api/logs")
def api_logs():
    try:
        return jsonify(ok=True, **engine.activity_filtered(
            limit=request.args.get("limit",200),
            offset=request.args.get("offset",0),
            level=request.args.get("level") or None,
            event_type=request.args.get("event_type") or None,
            q=request.args.get("q") or None,
            sort=request.args.get("sort") or "created_at",
            direction=request.args.get("direction") or "desc"))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.get("/api/downloads")
def api_downloads():
    return jsonify(results=engine.downloads(max(1,min(1000,int(request.args.get("limit","200"))))))

@app.get("/api/providers")
def api_providers():
    return jsonify(results=engine.provider_public())

@app.get("/api/downloaders")
def api_downloaders():
    return jsonify(config=engine.downloader_config_public())

@app.post("/api/downloaders/test")
def api_test_downloaders():
    return jsonify(results=engine.test_downloaders())

@app.get("/api/downloaders/monitor")
def api_downloaders_monitor():
    try:
        return jsonify(engine.downloader_monitor(request.args.get("limit",200)))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.get("/api/downloaders/readiness")
def api_downloaders_readiness():
    try:
        return jsonify(engine.downloader_readiness_check())
    except Exception as e:
        return jsonify(error=str(e)),400

@app.post("/api/downloaders/test/start")
def api_test_downloaders_start():
    def worker(job_id):
        job_center.update_job(job_id, stage="Downloader test", message="Checking configured downloader settings.", percent=10, total=3)
        readiness=engine.downloader_readiness_check()
        job_center.update_job(job_id, stage="Downloader test", message="Testing configured downloader connection(s).", percent=35, processed=1, total=3, result={"readiness":readiness})
        results=engine.test_downloaders()
        failed=len([r for r in results if not r.get("ok")])
        job_center.update_job(job_id, status="complete" if not failed else "error", stage="Complete" if not failed else "Needs attention",
                              message="Downloader connection test complete." if not failed else f"{failed} downloader test(s) failed.",
                              percent=100, processed=3, succeeded=len(results)-failed, failed=failed, total=3, result={"readiness":readiness,"results":results})
        return {"readiness":readiness,"results":results}
    return jsonify(ok=True, job=job_center.run_background("downloader_connection_test", worker, stage="Queued", message="Downloader test queued.", total=3))

@app.post("/api/downloaders/poll/start")
def api_poll_downloaders_start():
    def worker(job_id):
        job_center.update_job(job_id, stage="Downloader monitor", message="Polling configured downloader queue(s).", percent=20, total=2)
        result=engine.poll_downloaders()
        errors=len([r for r in result.get("results",[]) if r.get("error")])
        job_center.update_job(job_id, status="complete" if not errors else "error", stage="Complete" if not errors else "Needs attention",
                              message="Downloader polling complete." if not errors else f"{errors} downloader poll error(s).",
                              percent=100, processed=2, succeeded=len(result.get("results",[]))-errors, failed=errors, total=2, result=result)
        return result
    return jsonify(ok=True, job=job_center.run_background("downloader_queue_poll", worker, stage="Queued", message="Downloader polling queued.", total=2))

@app.post("/api/downloads/monitor/start")
def api_downloads_monitor_start():
    def worker(job_id):
        job_center.update_job(job_id, stage="Download monitor", message="Reading local download history and handoff candidates.", percent=25, total=4)
        monitor=engine.downloader_monitor(limit=200)
        job_center.update_job(job_id, stage="Download monitor", message="Checking downloader readiness.", percent=60, processed=2, total=4, result=monitor)
        readiness=engine.downloader_readiness_check()
        result={"monitor":monitor,"readiness":readiness}
        job_center.update_job(job_id, status="complete", stage="Complete", message="Download monitor refreshed.", percent=100, processed=4, succeeded=4, total=4, result=result)
        return result
    return jsonify(ok=True, job=job_center.run_background("download_monitor_refresh", worker, stage="Queued", message="Download monitor refresh queued.", total=4))

@app.post("/api/episodes/<int:eid>/search")
def api_episode_search(eid):
    body=request.get_json(silent=True) or {}
    try:
        return jsonify(engine.search_episode(eid,auto_grab=bool(body.get("auto_grab",False))))
    except Exception as e:
        return jsonify(error=str(e)),400


@app.get("/api/shows/<int:sid>/missing-search/preview")
def api_show_missing_preview(sid):
    import show_missing_search
    try:
        return jsonify(total=len(show_missing_search.candidates(sid)), simulation=engine.as_bool(engine.get_setting("TVManager","simulation_mode","0")))
    except ValueError as exc:
        return jsonify(error=str(exc)),400

@app.post("/api/shows/<int:sid>/missing-search/start")
def api_show_missing_start(sid):
    import show_missing_search
    try:
        return jsonify(ok=True, job=show_missing_search.start(sid))
    except ValueError as exc:
        return jsonify(error=str(exc)),400


@app.post("/api/episodes/<int:eid>/search/start")
def api_episode_search_start(eid):
    body=request.get_json(silent=True) or {}
    auto_grab=bool(body.get("auto_grab",False))
    def worker(job_id):
        job_center.update_job(job_id, stage="Episode search", message="Searching configured providers.", percent=10, total=1)
        result=engine.search_episode(eid,auto_grab=auto_grab)
        job_center.update_job(job_id, status="complete", stage="Complete", message="Episode search complete.", percent=100, result=result, processed=1, succeeded=1)
        return result
    return jsonify(ok=True, job=job_center.run_background("episode_search", worker, stage="Queued", message="Episode search queued.", meta={"episode_id":eid,"auto_grab":auto_grab}))

@app.post("/api/search/run/<kind>/start")
def api_run_search_start(kind):
    if kind not in {"recent","backlog"}:
        return jsonify(error="kind must be recent or backlog"),400
    body=request.get_json(silent=True) or {}
    auto_grab=bool(body.get("auto_grab",False))
    def worker(job_id):
        job_center.update_job(job_id, stage=f"{kind.title()} search", message="Searching missing episodes in the background.", percent=5)
        result=engine.run_search_job(kind,auto_grab=auto_grab)
        searched=len(result.get("searched") or result.get("results") or []) if isinstance(result,dict) else 0
        job_center.update_job(job_id, status="complete", stage="Complete", message=f"{kind.title()} search complete.", percent=100, result=result, processed=searched, succeeded=searched)
        return result
    return jsonify(ok=True, job=job_center.run_background(kind+"_search", worker, stage="Queued", message=f"{kind.title()} search queued.", meta={"auto_grab":auto_grab}))

@app.get("/api/episodes/<int:eid>/results")
def api_episode_results(eid):
    with cx() as c:
        rows=c.execute("SELECT * FROM search_results WHERE episode_id=? ORDER BY rejected_reason IS NOT NULL,score DESC,id DESC",(eid,)).fetchall()
    return jsonify(results=[dict(r) for r in rows])

@app.post("/api/search-results/<int:rid>/grab")
def api_grab_result(rid):
    try:
        return jsonify(engine.grab_result(rid))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.post("/api/search-results/<int:rid>/grab/start")
def api_grab_result_start(rid):
    def worker(job_id):
        try:
            job_center.update_job(job_id, stage="Downloader handoff", message="Validating selected release and configured download client.", percent=10, total=1)
            job_center.update_job(job_id, stage="Downloader handoff", message="Sending release to configured downloader.", percent=45, processed=0, total=1)
            result=engine.grab_result(rid)
            job_center.update_job(job_id, status="complete", stage="Queued", message=f"Queued in {result.get('client','downloader')}.", percent=100, result=result, processed=1, succeeded=1, total=1)
            return result
        except Exception as exc:
            job_center.append_error(job_id, {"search_result_id":rid,"error":str(exc)})
            job_center.update_job(job_id, status="error", stage="Downloader handoff failed", message=str(exc), percent=100, processed=1, failed=1, total=1)
            raise
    return jsonify(ok=True, job=job_center.run_background("downloader_handoff", worker, stage="Queued", message="Downloader handoff queued.", meta={"search_result_id":rid}))

@app.post("/api/search/run/<kind>")
def api_run_search(kind):
    if kind not in {"recent","backlog"}:
        return jsonify(error="kind must be recent or backlog"),400
    body=request.get_json(silent=True) or {}
    try:
        return jsonify(engine.run_search_job(kind,auto_grab=bool(body.get("auto_grab",False))))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.get("/api/scheduler")
def api_scheduler():
    return jsonify(
        automation_enabled=engine.as_bool(engine.get_setting("TVManager","automation_enabled","0")),
        auto_grab=engine.as_bool(engine.get_setting("TVManager","auto_grab","1")),
        jobs=engine.jobs_public()
    )

@app.post("/api/scheduler/automation")
def api_scheduler_automation():
    body=request.get_json(silent=True) or {}
    return jsonify(engine.set_automation(bool(body.get("enabled"))))

@app.post("/api/scheduler/jobs/<name>")
def api_scheduler_job(name):
    body=request.get_json(silent=True) or {}
    engine.update_job(name,body.get("enabled") if "enabled" in body else None,body.get("interval"))
    return jsonify(ok=True,jobs=engine.jobs_public())

@app.post("/api/scheduler/jobs/<name>/run")
def api_scheduler_run(name):
    def worker(job_id):
        job_center.update_job(job_id, stage="Scheduler", message=f"Running {name.replace('_',' ')}.", percent=5)
        result=engine.run_job(name)
        status="complete" if result.get("ok", True) else "error"
        job_center.update_job(job_id, status=status, stage="Complete" if status=="complete" else "Error",
                              message=("Scheduler job complete." if status=="complete" else result.get("error") or result.get("message") or "Scheduler job failed."),
                              percent=100, result=result, processed=1, succeeded=1 if status=="complete" else 0, failed=0 if status=="complete" else 1)
        return result
    job=job_center.run_background("scheduler_"+name, worker, stage="Queued", message=f"{name.replace('_',' ')} queued.")
    return jsonify(ok=True, job=job)

@app.post("/api/settings/tvmanager")
def api_tvmanager_settings():
    body=request.get_json(silent=True) or {}
    allowed={"auto_grab","recent_days","max_searches_per_run","refresh_media_servers_after_process","simulation_mode","ignore_season_zero_counts","api_auth_enabled","metadata_missing_limit","artwork_refresh_limit","background_worker_limit"}
    for k,v in body.items():
        if k in allowed:
            engine.set_setting("TVManager",k,v)
    return jsonify(ok=True)

@app.patch("/api/episodes/<int:eid>")
def api_episode_update(eid):
    body=request.get_json(silent=True) or {}
    fields=[]; vals=[]
    if "status" in body:
        fields.append("status=?"); vals.append(str(body["status"]))
    if "monitored" in body:
        fields.append("monitored=?"); vals.append(1 if body["monitored"] else 0)
    if "ignored" in body:
        ignored=1 if body.get("ignored") else 0
        fields.append("ignored=?"); vals.append(ignored)
        fields.append("ignored_reason=?"); vals.append((body.get("ignored_reason") or "Manual episode ignore") if ignored else "")
        fields.append("ignored_at=CURRENT_TIMESTAMP" if ignored else "ignored_at=NULL")
        fields.append("ignored_source=?"); vals.append("episode_update" if ignored else None)
        if ignored and "status" not in body:
            fields.append("status='Ignored'")
        elif not ignored and "status" not in body:
            fields.append("status=CASE WHEN location IS NOT NULL AND TRIM(location)<>'' THEN 'Downloaded' ELSE 'Wanted' END")
    if "managed_note" in body:
        fields.append("managed_note=?"); vals.append(str(body.get("managed_note") or ""))
    if not fields:
        return jsonify(error="Nothing to update"),400
    vals.append(eid)
    with cx() as c:
        c.execute("UPDATE episodes SET "+",".join(fields)+" WHERE id=?",vals)
        c.commit()
    return jsonify(ok=True)

@app.post("/api/shows/<int:sid>/rename-preview")
def api_library_rename_preview(sid):
    import library_rename
    from itsdangerous import URLSafeTimedSerializer
    try:
        plan=library_rename.preview(DB,sid,engine.get_setting("General","naming_pattern","Season %0S/%SN - S%0SE%0E - %EN"),engine.as_bool(engine.get_setting("General","move_associated_files","1"),True))
        token=URLSafeTimedSerializer(app.secret_key,salt="library-rename").dumps(plan)
        return jsonify(plan=plan,token=token)
    except (ValueError,OSError) as exc:return jsonify(error=str(exc)),400

@app.post("/api/shows/<int:sid>/rename-apply")
def api_library_rename_apply(sid):
    import library_rename, media_operations
    from itsdangerous import URLSafeTimedSerializer, BadData
    body=request.get_json() or {}
    try:
        plan=URLSafeTimedSerializer(app.secret_key,salt="library-rename").loads(body.get("token",""),max_age=1800)
        if plan['show_id']!=sid:raise ValueError("Preview belongs to another show")
        with media_operations.exclusive(BASE):
            result=library_rename.apply(DB,plan,body.get("selected",[]),BASE/"rename-journals")
        return jsonify(ok=True,**result)
    except BadData:return jsonify(error="Preview expired or is invalid. Preview again."),400
    except (ValueError,OSError) as exc:return jsonify(error=str(exc)),400

@app.get("/notifications")
def native_notifications_page():return render_template("notifications.html")

@app.get("/api/notification-services")
def native_notifications_list():
    import notifiers
    return jsonify(results=notifiers.listing())

@app.post("/api/notification-services")
def native_notifications_save():
    import notifiers
    try:return jsonify(ok=True,id=notifiers.save(request.get_json() or {}))
    except ValueError as exc:return jsonify(error=str(exc)),400

@app.delete("/api/notification-services/<int:sid>")
def native_notifications_remove(sid):
    import notifiers
    try:notifiers.remove(sid);return jsonify(ok=True)
    except ValueError as exc:return jsonify(error=str(exc)),400

@app.post("/api/notification-services/<int:sid>/test")
def native_notifications_test(sid):
    import notifiers
    try:return jsonify(results=notifiers.dispatch("test",{"message":"TV Manager test notification"},only_id=sid))
    except ValueError as exc:return jsonify(error=str(exc)),400

@app.post("/api/shows/<int:sid>/scene-refresh")
def api_scene_refresh(sid):
    import scene_sync
    try:return jsonify(ok=True,**scene_sync.refresh(sid,force=True))
    except ValueError as exc:return jsonify(error=str(exc)),400

@app.get("/metadata-sources")
def metadata_sources_page():return render_template('metadata_sources.html')

@app.get("/api/metadata-sources/tvdb")
def tvdb_config_status():
    import tvdb_client
    key,pin=tvdb_client.credentials(DB)
    return jsonify(configured=bool(key),api_key='********' if key else '',pin='********' if pin else '')

@app.put("/api/metadata-sources/tvdb")
def tvdb_config_save():
    body=request.get_json() or {}
    for field in ('api_key','pin'):
        if field in body and body[field]!='********':engine.set_setting('TVDB',field,str(body[field] or '').strip(),is_secret=1)
    return jsonify(ok=True)

@app.get("/api/shows/defaults")
def api_show_defaults():
    import show_preferences
    with cx(readonly=True) as c:return jsonify(preferences=show_preferences.defaults(c))

@app.put("/api/shows/defaults")
def api_save_show_defaults():
    import show_preferences
    try:
        with cx() as c:values=show_preferences.save_defaults(c,request.get_json() or {})
        return jsonify(ok=True,preferences=values)
    except ValueError as exc:return jsonify(error=str(exc)),400

@app.patch("/api/shows/<int:sid>/options")
def api_show_options(sid):
    body=request.get_json(silent=True) or {}
    import show_preferences
    try: values=show_preferences.options(body,allow_name=True)
    except ValueError as exc: return jsonify(error=str(exc)),400
    if not values:return jsonify(error="Nothing to update"),400
    with cx() as c:
        if not c.execute("SELECT id FROM shows WHERE id=?",(sid,)).fetchone():return jsonify(error="Show not found"),404
        for field,table in (("quality_profile_id","quality_profiles"),("retention_policy_id","retention_policies")):
            if values.get(field) and not c.execute(f"SELECT id FROM {table} WHERE id=?",(values[field],)).fetchone():return jsonify(error="Selected profile no longer exists"),400
        c.execute("UPDATE shows SET "+",".join(k+"=?" for k in values)+" WHERE id=?",[*values.values(),sid])
    return jsonify(ok=True)


@app.get("/api/postprocess/config")
def api_postprocess_config():
    return jsonify(
        tv_download_dir=engine.get_setting("General","tv_download_dir","") or "",
        process_method=engine.get_setting("General","process_method","move") or "move",
        process_automatically=engine.as_bool(engine.get_setting("General","process_automatically","0"),False),
        rename_episodes=engine.as_bool(engine.get_setting("General","rename_episodes","1"),True),
        move_associated_files=engine.as_bool(engine.get_setting("General","move_associated_files","1"),True),
        simulation_mode=engine.as_bool(engine.get_setting("TVManager","simulation_mode","0"),False),
    )

@app.post("/api/postprocess/config")
def api_postprocess_config_save():
    body=request.get_json(silent=True) or {}
    allowed={"tv_download_dir","process_method","process_automatically","rename_episodes","move_associated_files"}
    for k,v in body.items():
        if k in allowed:
            engine.set_setting("General",k,str(v))
    return jsonify(ok=True)

@app.get("/api/postprocess/scan")
def api_postprocess_scan():
    root=request.args.get("root") or None
    limit=max(1,min(1000,int(request.args.get("limit","300"))))
    return jsonify(engine.scan_postprocess(dry_run=True,root_override=root,limit=limit))

@app.post("/api/postprocess/scan/start")
def api_postprocess_scan_start():
    body=request.get_json(silent=True) or {}
    root=body.get("root") or request.args.get("root") or None
    limit=max(1,min(1000,int(body.get("limit") or request.args.get("limit","300"))))
    def worker(job_id):
        def progress(u):
            job_center.update_job(job_id, **u)
        result=engine.scan_postprocess(dry_run=True,root_override=root,limit=limit,progress_callback=progress)
        job_center.update_job(job_id, status="complete", stage="Preview complete", message="Post-processing preview scan complete.", percent=100, result=result, processed=result.get("files",0), succeeded=result.get("matched",0), failed=result.get("unmatched",0), total=result.get("files",0))
        return result
    return jsonify(ok=True, job=job_center.run_background("postprocess_scan", worker, stage="Queued", message="Post-processing folder scan queued.", meta={"root":root,"limit":limit}))

@app.post("/api/postprocess/run/start")
def api_postprocess_run_start():
    body=request.get_json(silent=True) or {}
    selected=body.get("selected_sources") or body.get("sources") or None
    limit=max(1,min(1000,int(body.get("limit",300))))
    root=body.get("root") or None
    method=body.get("process_method") or None
    def worker(job_id):
        job_center.update_job(job_id, stage="Post-processing", message="Processing approved files.", percent=10)
        result=engine.scan_postprocess(dry_run=False,root_override=root,limit=limit,selected_sources=selected,process_method_override=method,progress_callback=lambda u: job_center.update_job(job_id, **u))
        processed=len(result.get("processed") or result.get("results") or []) if isinstance(result,dict) else 0
        job_center.update_job(job_id, status="complete", stage="Complete", message="Post-processing complete.", percent=100, result=result, processed=processed, succeeded=processed)
        return result
    return jsonify(ok=True, job=job_center.run_background("post_processing", worker, stage="Queued", message="Post-processing queued.", meta={"root":root,"limit":limit,"method":method}))

@app.post("/api/postprocess/run")
def api_postprocess_run():
    body=request.get_json(silent=True) or {}
    try:
        selected=body.get("selected_sources") or body.get("sources") or None
        limit=max(1,min(1000,int(body.get("limit",300))))
        root=body.get("root") or None
        method=body.get("process_method") or None
        return jsonify(engine.scan_postprocess(dry_run=False,root_override=root,limit=limit,selected_sources=selected,process_method_override=method))
    except Exception as e:
        return jsonify(error=str(e)),400


@app.get("/api/tvmanager/config")
def api_tvmanager_config():
    return jsonify(
        automation_enabled=engine.as_bool(engine.get_setting("TVManager","automation_enabled","0")),
        auto_grab=engine.as_bool(engine.get_setting("TVManager","auto_grab","1")),
        recent_days=engine.as_int(engine.get_setting("TVManager","recent_days","14"),14),
        max_searches_per_run=engine.as_int(engine.get_setting("TVManager","max_searches_per_run","25"),25),
        metadata_missing_limit=engine.as_int(engine.get_setting("TVManager","metadata_missing_limit","200"),200),
        artwork_refresh_limit=engine.as_int(engine.get_setting("TVManager","artwork_refresh_limit","200"),200),
        background_worker_limit=engine.as_int(engine.get_setting("TVManager","background_worker_limit","4"),4),
        ignore_season_zero_counts=engine.as_bool(engine.get_setting("TVManager","ignore_season_zero_counts","1"),True),
    )

@app.patch("/api/shows/<int:sid>/seasons/<int:season>")
def api_season_update(sid,season):
    body=request.get_json(silent=True) or {}
    fields=[];vals=[]
    if "status" in body:
        fields.append("status=?");vals.append(str(body["status"]))
    if "monitored" in body:
        fields.append("monitored=?");vals.append(1 if body["monitored"] else 0)
    if not fields:
        return jsonify(error="Nothing to update"),400
    vals.extend([sid,season])
    with cx() as c:
        cur=c.execute("UPDATE episodes SET "+",".join(fields)+" WHERE show_id=? AND season=?",vals)
        c.commit()
    engine.log("season_update",f"Updated season {season}: {cur.rowcount} episodes",show_id=sid,data=body)
    return jsonify(ok=True,updated=cur.rowcount)

def _scan_show_library_impl(sid, progress_callback=None):
    with cx() as c:
        show=c.execute("SELECT * FROM shows WHERE id=?",(sid,)).fetchone()
    if not show:
        raise ValueError("Show not found")
    root=show["location"]
    if not root:
        raise ValueError("This show has no library folder configured.")
    from pathlib import Path
    p=Path(root)
    if not p.exists():
        raise ValueError("The configured show folder is not reachable from this computer.")
    media={".mkv",".mp4",".avi",".m4v",".mov",".ts",".mpeg",".mpg",".wmv"}
    if progress_callback:
        progress_callback({"stage":"Counting files","message":"Checking configured show folder before scan.","percent":5,"current_show":show["name"]})
    all_files=[f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in media]
    total=max(1,len(all_files))
    matched=0;files=0;unmatched=[]
    if progress_callback:
        progress_callback({"stage":"Scanning existing files","message":f"Scanning {len(all_files)} media files for {show['name']}.","percent":10,"total":len(all_files),"processed":0,"succeeded":0,"failed":0,"current_show":show["name"]})
    for f in all_files:
        files+=1
        if progress_callback and (files == 1 or files % 10 == 0 or files == len(all_files)):
            progress_callback({"stage":"Scanning existing files","message":str(f),"percent":10+int((files/total)*80),"total":len(all_files),"processed":files,"succeeded":matched,"failed":len(unmatched),"current_show":show["name"]})
        pairs=advanced.split_multi_episode(f.name)
        if not pairs:
            pat=engine.episode_pattern(f)
            pairs=[pat] if pat else []
        if not pairs:
            if len(unmatched)<30: unmatched.append(str(f))
            continue
        found_any=False
        with cx() as c:
            for season,ep in pairs:
                e=c.execute("SELECT id FROM episodes WHERE show_id=? AND season=? AND episode=?",(sid,season,ep)).fetchone()
                if e:
                    c.execute("UPDATE episodes SET location=?,file_size=?,status='Downloaded' WHERE id=?",
                              (str(f),f.stat().st_size,e["id"]))
                    matched+=1;found_any=True
            c.commit()
        if found_any:
            try: integrity.cache_fingerprint(f)
            except Exception: pass
        elif len(unmatched)<30:
            unmatched.append(str(f))
    engine.log("library_scan",f'{show["name"]}: scanned {files} files, matched {matched}',show_id=sid)
    return {"ok":True,"files":files,"matched":matched,"unmatched":unmatched,"show":show["name"]}

@app.post("/api/shows/<int:sid>/scan-library")
def api_scan_show_library(sid):
    try:
        return jsonify(_scan_show_library_impl(sid))
    except ValueError as e:
        msg=str(e); return jsonify(error=msg),404 if msg == "Show not found" else 400
    except Exception as e:
        return jsonify(error=str(e)),500

@app.post("/api/shows/<int:sid>/scan-library/start")
def api_scan_show_library_start(sid):
    def worker(job_id):
        result=_scan_show_library_impl(sid, progress_callback=lambda u: job_center.update_job(job_id, **u))
        job_center.update_job(job_id, status="complete", stage="Scan complete", message=f"Scanned {result.get('files',0)} files and matched {result.get('matched',0)} episodes.", percent=100, result=result, processed=result.get("files",0), succeeded=result.get("matched",0), failed=len(result.get("unmatched") or []), total=result.get("files",0))
        return result
    return jsonify(ok=True, job=job_center.run_background("show_folder_scan", worker, stage="Queued", message="Show folder scan queued. You can switch screens and monitor it from Active Jobs.", meta={"show_id":sid}))

@app.get("/api/health")
def api_health():
    with cx() as c:
        counts={}
        for table in ("shows","episodes","search_results","downloads","activity_log"):
            counts[table]=c.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]
    return jsonify(ok=True,counts=counts,providers=len(engine.provider_public()),
                   downloader_config=engine.downloader_config_public(),
                   automation=engine.as_bool(engine.get_setting("TVManager","automation_enabled","0")),
                   backup_dir=str(BACKUPS))


@app.get("/api/dashboard/full")
def api_dashboard_full():
    health_summary=library_maintenance.library_health_report(DB,duplicate_limit=5,sample_limit=5)
    return jsonify(stats=engine.dashboard_stats(),jobs=engine.jobs_public(),
                   activity=engine.activity(20),downloads=engine.downloads(20),
                   library_health=health_summary["counts"],recommendations=health_summary["recommendations"])

@app.get("/api/settings/sections")
def api_setting_sections():
    return jsonify(results=engine.setting_sections_public())

@app.get("/api/settings/section/<section>")
def api_setting_section(section):
    return jsonify(results=engine.settings_for_section(section))

@app.patch("/api/settings/section/<section>/<name>")
def api_setting_value(section,name):
    if section.lower()=="general" and name.lower()=="root_dirs":
        return jsonify(error="Manage library paths under Library Locations so shows-in-use checks are applied.",url="/library-storage"),400
    body=request.get_json(silent=True) or {}
    engine.update_setting_safe(section,name,body.get("value",""))
    return jsonify(ok=True)

@app.get("/api/quality-profiles")
def api_quality_profiles():
    return jsonify(results=engine.list_quality_profiles())

@app.post("/api/quality-profiles")
def api_quality_profile_create():
    body=request.get_json(silent=True) or {}
    try:
        return jsonify(ok=True,id=engine.save_quality_profile(body))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.patch("/api/quality-profiles/<int:pid>")
def api_quality_profile_update(pid):
    body=request.get_json(silent=True) or {}; body["id"]=pid
    try:
        return jsonify(ok=True,id=engine.save_quality_profile(body))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.delete("/api/quality-profiles/<int:pid>")
def api_quality_profile_delete(pid):
    try:
        engine.delete_quality_profile(pid); return jsonify(ok=True)
    except Exception as e:
        return jsonify(error=str(e)),400

@app.post("/api/downloads/<int:did>/fail")
def api_download_fail(did):
    body=request.get_json(silent=True) or {}
    try:
        return jsonify(engine.mark_release_failed(did,body.get("reason","Marked failed by user"),bool(body.get("retry",True))))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.get("/api/notifications")
def api_notifications():
    return jsonify(results=engine.notification_channels())

@app.post("/api/notifications/email/test")
def api_email_test():
    try:
        return jsonify(engine.send_test_email())
    except Exception as e:
        return jsonify(error=str(e)),400


@app.post("/api/shows/<int:sid>/write-metadata")
def api_write_metadata(sid):
    body=request.get_json(silent=True) or {}
    try:
        return jsonify(engine.write_show_metadata(
            sid,artwork=bool(body.get("artwork",True)),
            episode_nfo=bool(body.get("episode_nfo",True))))
    except Exception as e:
        return jsonify(error=str(e)),400

@app.post("/api/downloaders/poll")
def api_poll_downloaders():
    try:
        return jsonify(engine.poll_downloaders())
    except Exception as e:
        return jsonify(error=str(e)),400


@app.get("/advanced")
def advanced_page(): return render_template("advanced.html")

@app.get("/api/providers/custom")
def api_custom_providers(): return jsonify(results=advanced.provider_defs())

@app.post("/api/providers/custom")
def api_custom_provider_save():
    body=request.get_json(silent=True) or {}
    try:return jsonify(ok=True,id=advanced.save_provider(body))
    except Exception as e:return jsonify(error=str(e)),400

@app.delete("/api/providers/custom/<int:pid>")
def api_custom_provider_delete(pid):
    advanced.delete_provider(pid);return jsonify(ok=True)

@app.post("/api/providers/custom/<int:pid>/test")
def api_custom_provider_test(pid):
    try:return jsonify(advanced.test_provider(pid))
    except Exception as e:return jsonify(error=str(e)),400

@app.get("/api/shows/<int:sid>/scene-mappings")
def api_scene_mappings(sid): return jsonify(results=advanced.mappings(sid),aliases=advanced.aliases(sid))

@app.post("/api/shows/<int:sid>/scene-mappings")
def api_scene_mapping_save(sid):
    body=request.get_json(silent=True) or {}
    try:advanced.save_mapping(sid,body);return jsonify(ok=True)
    except Exception as e:return jsonify(error=str(e)),400

@app.delete("/api/scene-mappings/<int:mid>")
def api_scene_mapping_delete(mid):
    advanced.delete_mapping(mid);return jsonify(ok=True)

@app.get("/api/groups")
def api_groups(): return jsonify(results=advanced.groups())

@app.post("/api/groups")
def api_group_save():
    body=request.get_json(silent=True) or {}
    try:
        return jsonify(ok=True,id=advanced.save_group(body.get("name","New Group"),body.get("show_ids"),body.get("id"),body.get("sort_order")))
    except Exception as e:return jsonify(error=str(e)),400

@app.delete("/api/groups/<int:gid>")
def api_group_delete(gid):
    try:return jsonify(advanced.delete_group(gid))
    except Exception as e:return jsonify(error=str(e)),400

@app.get("/api/groups/<int:gid>/shows")
def api_group_shows(gid): return jsonify(results=advanced.group_shows(gid))

@app.get("/api/webhooks")
def api_webhooks(): return jsonify(results=advanced.webhooks())

@app.post("/api/webhooks")
def api_webhook_save():
    body=request.get_json(silent=True) or {}
    try:return jsonify(ok=True,id=advanced.save_webhook(body))
    except Exception as e:return jsonify(error=str(e)),400

@app.delete("/api/webhooks/<int:wid>")
def api_webhook_delete(wid):
    try:return jsonify(advanced.delete_webhook(wid))
    except Exception as e:return jsonify(error=str(e)),400

@app.get("/api/media-servers")
def api_media_servers(): return jsonify(results=advanced.media_servers())

@app.get("/api/media-servers/<int:sid>")
def api_media_server_get(sid):
    try:return jsonify(ok=True,server=advanced.media_server(sid))
    except Exception as e:return jsonify(error=str(e)),404

@app.post("/api/media-servers")
def api_media_server_save():
    body=request.get_json(silent=True) or {}
    try:return jsonify(ok=True,id=advanced.save_media_server(body))
    except Exception as e:return jsonify(error=str(e)),400

@app.delete("/api/media-servers/<int:sid>")
def api_media_server_delete(sid):
    try:return jsonify(advanced.delete_media_server(sid))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/media-servers/<int:sid>/test")
def api_media_server_test(sid):
    try:return jsonify(advanced.test_media_server(sid))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/media-servers/<int:sid>/test/start")
def api_media_server_test_start(sid):
    def worker(job_id):
        server=advanced.media_server(sid)
        job_center.update_job(job_id, stage="Media server test", message=f"Testing {server.get('name')}.", percent=25, total=1)
        result=advanced.test_media_server(sid)
        job_center.update_job(job_id, status="complete", stage="Complete", message=f"{server.get('name')} connected successfully.", percent=100, processed=1, succeeded=1, total=1, result=result)
        return result
    return jsonify(ok=True, job=job_center.run_background("media_server_test", worker, stage="Queued", message="Media server test queued.", meta={"media_server_id":sid}))

@app.post("/api/media-servers/<int:sid>/refresh")
def api_media_server_refresh(sid):
    try:return jsonify(advanced.refresh_media_server(sid))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/media-servers/<int:sid>/refresh/start")
def api_media_server_refresh_start(sid):
    def worker(job_id):
        server=advanced.media_server(sid)
        job_center.update_job(job_id, stage="Media server refresh", message=f"Requesting library refresh for {server.get('name')}.", percent=35, total=1)
        result=advanced.refresh_media_server(sid)
        job_center.update_job(job_id, status="complete", stage="Complete", message=f"Refresh request sent to {server.get('name')}.", percent=100, processed=1, succeeded=1, total=1, result=result)
        return result
    return jsonify(ok=True, job=job_center.run_background("media_server_refresh", worker, stage="Queued", message="Media server refresh queued.", meta={"media_server_id":sid}))

@app.get("/api/release/parse")
def api_release_parse():
    title=request.args.get("title","")
    return jsonify(episodes=advanced.split_multi_episode(title),quality=engine.infer_quality(title))


@app.get("/subtitles")
def subtitles_page(): return render_template("subtitles.html")

@app.get("/api/subtitles/scan")
def api_subtitle_scan():
    sid=request.args.get("show_id")
    try:return jsonify(engine.subtitle_scan(int(sid) if sid else None))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/subtitles/scan/start")
def api_subtitle_scan_start():
    body=request.get_json(silent=True) or {}
    sid=body.get("show_id") or request.args.get("show_id")
    show_id=int(sid) if sid else None
    def worker(job_id):
        def progress(u):
            job_center.update_job(job_id, **u)
        result=engine.subtitle_scan(show_id, progress_callback=progress)
        job_center.update_job(job_id, status="complete", stage="Subtitle audit complete", message="Subtitle audit complete.", percent=100, result=result, processed=result.get("checked",0), succeeded=result.get("present",0), failed=result.get("missing",0), total=result.get("checked",0))
        return result
    return jsonify(ok=True, job=job_center.run_background("subtitle_audit", worker, stage="Queued", message="Subtitle audit queued.", meta={"show_id":show_id}))

@app.post("/api/backup")
def api_backup():
    stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
    path=BACKUPS/f"tvmanager-backup-{stamp}.zip"
    manifest={"version":"6.1","created_at":datetime.now().isoformat(),"files":["tvmanager.db"]}
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as z:
        z.write(DB,"tvmanager.db")
        z.writestr("manifest.json",json.dumps(manifest,indent=2))
    with cx() as c:
        c.execute("INSERT INTO backup_history(path,kind,status) VALUES(?,'manual','OK')",(str(path),));c.commit()
    return jsonify(ok=True,path=str(path),filename=path.name)

@app.get("/api/backup/download/<name>")
def api_backup_download(name):
    safe=secure_filename(name);path=BACKUPS/safe
    if not path.exists():return jsonify(error="Backup not found"),404
    return send_file(path,as_attachment=True,download_name=safe)


@app.get("/operations")
def operations_page(): return render_template("operations.html")

@app.get("/api/operations/summary")
def api_operations_summary(): return jsonify(ops.operations_summary())

@app.get("/api/provider-health")
def api_provider_health(): return jsonify(results=ops.provider_health())

@app.get("/api/search-decisions/<int:eid>")
def api_search_decisions(eid): return jsonify(results=ops.decisions(eid))

@app.get("/api/automation-rules")
def api_automation_rules(): return jsonify(results=ops.rules())

@app.post("/api/automation-rules")
def api_automation_rule_save():
    body=request.get_json(silent=True) or {}
    try:return jsonify(ok=True,id=ops.save_rule(body))
    except Exception as e:return jsonify(error=str(e)),400

@app.delete("/api/automation-rules/<int:rid>")
def api_automation_rule_delete(rid):
    ops.delete_rule(rid);return jsonify(ok=True)

@app.get("/api/config-snapshots")
def api_config_snapshots(): return jsonify(results=ops.snapshots())

@app.post("/api/config-snapshots")
def api_config_snapshot_create():
    body=request.get_json(silent=True) or {}
    return jsonify(ok=True,**ops.create_snapshot(body.get("name") or f"Snapshot {datetime.now().isoformat(timespec='minutes')}"))

@app.post("/api/config-snapshots/start")
def api_config_snapshot_create_start():
    body=request.get_json(silent=True) or {}
    name=body.get("name") or f"Snapshot {datetime.now().isoformat(timespec='minutes')}"
    def worker(job_id):
        job_center.update_job(job_id, stage="Configuration snapshot", message="Capturing settings, providers, scheduler and automation tables.", percent=35)
        result=ops.create_snapshot(name)
        job_center.update_job(job_id, status="complete", stage="Snapshot complete", message=f"Configuration snapshot created: {name}", percent=100, result=result, processed=1, succeeded=1, total=1)
        return result
    return jsonify(ok=True, job=job_center.run_background("config_snapshot", worker, stage="Queued", message="Configuration snapshot queued.", meta={"name":name}))


@app.post("/api/config-snapshots/<int:sid>/restore")
def api_config_snapshot_restore(sid):
    try:return jsonify(ops.restore_snapshot(sid))
    except Exception as e:return jsonify(error=str(e)),400

@app.get("/api/path-mappings")
def api_path_mappings(): return jsonify(results=ops.path_mappings())

@app.post("/api/path-mappings")
def api_path_mapping_save():
    body=request.get_json(silent=True) or {}
    try:return jsonify(ok=True,id=ops.save_path_mapping(body))
    except Exception as e:return jsonify(error=str(e)),400

@app.get("/api/library/root-health")
def api_root_health(): return jsonify(ops.root_health())

@app.post("/api/library/root-health/start")
def api_root_health_start():
    def worker(job_id):
        job_center.update_job(job_id, stage="Root path scan", message="Checking configured library roots and path mappings.", percent=20)
        result=ops.root_health()
        job_center.update_job(job_id, status="complete", stage="Path check complete", message=f"{result.get('reachable',0)}/{result.get('checked',0)} paths reachable; {result.get('missing',0)} missing.", percent=100, result=result, processed=result.get("checked",0), succeeded=result.get("reachable",0), failed=result.get("missing",0), total=result.get("checked",0))
        return result
    return jsonify(ok=True, job=job_center.run_background("root_path_health", worker, stage="Queued", message="Root/path health scan queued."))


@app.get("/api/library/conflicts")
def api_library_conflicts(): return jsonify(results=ops.detect_conflicts())

@app.post("/api/library/conflicts/start")
def api_library_conflicts_start():
    def worker(job_id):
        job_center.update_job(job_id, stage="Conflict scan", message="Scanning library records for duplicates and path conflicts.", percent=25)
        results=ops.detect_conflicts()
        job_center.update_job(job_id, status="complete", stage="Conflict scan complete", message=f"Found {len(results)} conflicts requiring review.", percent=100, result={"results":results}, processed=len(results), succeeded=0, failed=len(results), total=len(results))
        return {"results":results}
    return jsonify(ok=True, job=job_center.run_background("library_conflict_scan", worker, stage="Queued", message="Library conflict scan queued."))


@app.get("/api/library/duplicates")
def api_library_duplicates_v17():
    try:
        limit=int(request.args.get("limit",100))
    except Exception:
        limit=100
    return jsonify(results=library_maintenance.duplicate_candidates(DB,limit=max(1,min(limit,500))))

@app.get("/api/library/health-report")
@app.get("/api/library/health-report/")
@app.get("/api/library-health/report")
def api_library_health_report_v171():
    try:
        duplicate_limit=int(request.args.get("duplicate_limit",25))
        sample_limit=int(request.args.get("sample_limit",25))
    except Exception:
        duplicate_limit=25; sample_limit=25
    try:
        return jsonify(library_maintenance.library_health_report(
            DB,
            duplicate_limit=max(1,min(duplicate_limit,100)),
            sample_limit=max(1,min(sample_limit,100)),
        ))
    except Exception as ex:
        # Library Health is an operations screen; return a renderable payload instead
        # of a browser-breaking 500 so the UI can show the operator what failed.
        return jsonify(ok=False,error=str(ex),counts={},samples={},recommendations=["Open System and run setup/migrations, then reload Library Health."]),200

@app.post("/api/library/duplicates/preview")
def api_duplicate_cleanup_preview_v171():
    body=request.get_json(silent=True) or {}
    try:
        return jsonify(library_maintenance.duplicate_cleanup_preview(
            DB,keep_path=body.get("keep_path"),paths=body.get("paths") or None,limit=max(1,min(int(body.get("limit") or 100),500))))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/library/duplicates/apply")
def api_duplicate_cleanup_apply_v171():
    body=request.get_json(silent=True) or {}
    actions=body.get("actions") or []
    if not isinstance(actions,list) or not actions:
        return jsonify(error="Provide explicit duplicate cleanup actions from preview."),400
    try:
        return jsonify(library_maintenance.apply_duplicate_cleanup(DB,trash_root=MANAGED_TRASH,actions=actions))
    except Exception as e:return jsonify(error=str(e)),400

# ---- v17.14 professional job/protection center ----

@app.get("/database-safety")
@app.get("/database-safety/")
def database_safety_page():
    return render_template("database_safety.html")

@app.get("/jobs")
@app.get("/jobs/")
def jobs_page():
    return render_template("jobs.html")

@app.get("/api/jobs")
def api_jobs():
    return jsonify(ok=True, jobs=job_center.list_jobs(request.args.get("kind") or None))

@app.get("/api/jobs/<job_id>")
def api_job(job_id):
    job=job_center.get_job(job_id)
    if not job:
        return jsonify(error="Job not found."),404
    return jsonify(ok=True, job=job)

@app.get("/api/protection/status")
def api_protection_status():
    db=database_safety.quick_check(DB)
    backups=database_safety.scan_backups()
    return jsonify(ok=True, database=db, backups={
        "count": backups.get("count",0),
        "newest_usable_backup": backups.get("newest_usable_backup"),
    })

@app.post("/api/protection/backup")
def api_protection_backup():
    body=request.get_json(silent=True) or {}
    reason=str(body.get("reason") or "manual").strip().replace(" ","-")[:40] or "manual"
    include_secrets=bool(body.get("include_secrets"))
    def worker(job_id):
        job_center.update_job(job_id, stage="Database backup", message="Creating verified SQLite backup.", percent=20)
        result=database_safety.protect_now(reason=reason, include_config=True, include_secrets=include_secrets)
        job_center.update_job(job_id, stage="Verification", message="Scanning backup health.", percent=80)
        result["backups"]=database_safety.scan_backups()
        job_center.update_job(job_id, status="complete", stage="Protected", message="Database and configuration protection complete.", percent=100, result=result)
        return result
    return jsonify(ok=True, job=job_center.run_background("database_protection", worker, stage="Queued", message="Database/config protection queued."))

@app.get("/api/protection/backups")
def api_protection_backups():
    return jsonify(database_safety.scan_backups())

@app.post("/api/library/health-scan/start")
def api_library_health_scan_start():
    body=request.get_json(silent=True) or {}
    duplicate_limit=max(1,min(int(body.get("duplicate_limit") or 25),100))
    sample_limit=max(1,min(int(body.get("sample_limit") or 25),100))
    def worker(job_id):
        job_center.update_job(job_id, stage="Database safety", message="Checking SQLite database integrity.", percent=10)
        db_status=database_safety.quick_check(DB)
        if not db_status.get("ok"):
            raise RuntimeError("Database integrity check failed: " + str(db_status.get("error") or db_status.get("quick_check")))
        job_center.update_job(job_id, stage="Library scan", message="Scanning paths, metadata gaps, duplicates and missing files.", percent=35)
        report=library_maintenance.library_health_report(DB, duplicate_limit=duplicate_limit, sample_limit=sample_limit)
        job_center.update_job(job_id, stage="Protection check", message="Checking backup availability.", percent=75)
        protection=database_safety.scan_backups()
        report["database"] = db_status
        report["protection"] = {"backup_count": protection.get("count",0), "newest_usable_backup": protection.get("newest_usable_backup")}
        job_center.update_job(job_id, status="complete", stage="Complete", message="Library health scan complete.", percent=100, result=report, processed=1, succeeded=1)
        return report
    return jsonify(ok=True, job=job_center.run_background("library_health_scan", worker, stage="Queued", message="Library health scan queued."))

@app.get("/api/library/health-scan/jobs/<job_id>")
def api_library_health_scan_job(job_id):
    job=job_center.get_job(job_id)
    if not job or job.get("kind")!="library_health_scan":
        return jsonify(error="Library health scan job not found."),404
    return jsonify(ok=True, job=job)


@app.post("/api/metadata/refresh/missing/preview")
def api_metadata_refresh_missing_preview():
    body=request.get_json(silent=True) or {}
    try:
        return jsonify(metadata_service.missing_metadata_preview(
            limit=int(body.get("limit") or engine.get_setting("TVManager","metadata_missing_limit","200") or 200),
            include_paused=bool(body.get("include_paused"))
        ))
    except Exception as e:
        return metadata_error_response(e,500)

@app.post("/api/metadata/refresh/missing/start")
def api_metadata_refresh_missing_start():
    body=request.get_json(silent=True) or {}
    try:
        return jsonify(ok=True, job=metadata_service.start_missing_metadata_refresh(
            limit=int(body.get("limit") or engine.get_setting("TVManager","metadata_missing_limit","200") or 200),
            include_paused=bool(body.get("include_paused")),
            delay_seconds=float(body.get("delay_seconds") or 0.15)
        ))
    except Exception as e:
        return metadata_error_response(e,500)

@app.post("/api/metadata/artwork/preview")
def api_metadata_artwork_preview():
    body=request.get_json(silent=True) or {}
    try:
        return jsonify(metadata_service.artwork_preview(
            limit=int(body.get("limit") or engine.get_setting("TVManager","artwork_refresh_limit","200") or 200),
            include_episodes=bool(body.get("include_episodes", True))
        ))
    except Exception as e:
        return metadata_error_response(e,500)

@app.post("/api/metadata/artwork/start")
def api_metadata_artwork_start():
    body=request.get_json(silent=True) or {}
    try:
        return jsonify(ok=True, job=metadata_service.start_artwork_refresh(
            limit=int(body.get("limit") or engine.get_setting("TVManager","artwork_refresh_limit","200") or 200),
            include_episodes=bool(body.get("include_episodes", True))
        ))
    except Exception as e:
        return metadata_error_response(e,500)

@app.get("/api/metadata/status")
def api_metadata_status():
    return jsonify(ok=True, tmdb=metadata_service.tmdb_status())

@app.post("/api/metadata/refresh/run")
def api_metadata_refresh_run():
    body=request.get_json(silent=True) or {}
    batch_size=int(body.get("batch_size") or 5)
    try:
        return jsonify(ok=True,**metadata_service.refresh_batch(batch_size=max(1,min(batch_size,50))))
    except Exception as e:
        return metadata_error_response(e,500)


@app.post("/api/metadata/refresh/full/preview")
def api_metadata_refresh_full_preview():
    body=request.get_json(silent=True) or {}
    try:
        return jsonify(metadata_service.full_refresh_preview(
            include_paused=bool(body.get("include_paused")),
            stale_only=bool(body.get("stale_only"))
        ))
    except Exception as e:
        return metadata_error_response(e,500)

@app.post("/api/metadata/refresh/full/start")
def api_metadata_refresh_full_start():
    body=request.get_json(silent=True) or {}
    try:
        return jsonify(ok=True, job=metadata_service.start_full_refresh(
            batch_size=int(body.get("batch_size") or 10),
            include_paused=bool(body.get("include_paused")),
            stale_only=bool(body.get("stale_only")),
            delay_seconds=float(body.get("delay_seconds") or 0.15)
        ))
    except Exception as e:
        return metadata_error_response(e,500)

@app.get("/api/metadata/refresh/full/jobs")
def api_metadata_refresh_full_jobs():
    return jsonify(ok=True, jobs=metadata_service.full_refresh_jobs())

@app.get("/api/metadata/refresh/full/jobs/<job_id>")
def api_metadata_refresh_full_job(job_id):
    job=metadata_service.full_refresh_job(job_id)
    if not job:
        return jsonify(error="Metadata refresh job not found."),404
    return jsonify(ok=True, job=job)


@app.get("/queue")
def queue_page(): return render_template("queue.html")

@app.get("/api/command/search")
def api_command_search():
    return jsonify(results=intelligence.command_search(request.args.get("q","")))

@app.get("/api/insights")
def api_insights(): return jsonify(results=intelligence.dashboard_insights())

@app.get("/api/tags")
def api_tags(): return jsonify(results=intelligence.tags())

@app.post("/api/tags")
def api_tag_save():
    body=request.get_json(silent=True) or {}
    try:return jsonify(ok=True,id=intelligence.save_tag(body.get("name","Tag"),body.get("color","slate"),body.get("id")))
    except Exception as e:return jsonify(error=str(e)),400

@app.delete("/api/tags/<int:tid>")
def api_tag_delete(tid):
    try:return jsonify(intelligence.delete_tag(tid))
    except Exception as e:return jsonify(error=str(e)),400

@app.get("/api/shows/<int:sid>/tags")
def api_show_tags(sid): return jsonify(results=intelligence.tags_for_show(sid))

@app.post("/api/shows/<int:sid>/tags")
def api_show_tags_save(sid):
    body=request.get_json(silent=True) or {}
    intelligence.set_show_tags(sid,body.get("tag_ids") or []);return jsonify(ok=True)

@app.get("/api/saved-filters")
def api_saved_filters(): return jsonify(results=intelligence.saved_filters())

@app.post("/api/saved-filters")
def api_saved_filter_save():
    body=request.get_json(silent=True) or {}
    intelligence.save_filter(body.get("name","Saved Filter"),body.get("query") or {});return jsonify(ok=True)

@app.get("/api/retention-policies")
def api_retention_policies(): return jsonify(results=intelligence.retention_policies())

@app.post("/api/retention-policies")
def api_retention_policy_save():
    body=request.get_json(silent=True) or {}
    try:return jsonify(ok=True,id=intelligence.save_retention(body))
    except Exception as e:return jsonify(error=str(e)),400

@app.delete("/api/retention-policies/<int:pid>")
def api_retention_policy_delete(pid):
    try:return jsonify(intelligence.delete_retention(pid))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/episodes/<int:eid>/lock")
def api_episode_lock(eid):
    body=request.get_json(silent=True) or {}
    intelligence.lock_episode(eid,bool(body.get("locked",True)),body.get("reason","Protected"));return jsonify(ok=True)

@app.get("/api/queue/triage")
def api_queue_triage(): return jsonify(results=intelligence.queue_triage())

@app.post("/api/queue/<int:did>/note")
def api_queue_note(did):
    body=request.get_json(silent=True) or {}
    intelligence.add_queue_note(did,body.get("note",""));return jsonify(ok=True)

@app.get("/api/season-pack-plan/<int:sid>/<int:season>")
def api_season_pack_plan(sid,season):
    try:return jsonify(intelligence.season_pack_plan(sid,season))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/library/filter")
def api_library_filter():
    return jsonify(results=intelligence.filter_library(request.get_json(silent=True) or {}))


@app.get("/system")
def system_page(): return render_template("system.html")

@app.get("/api/system/health")
def api_system_health(): return jsonify(results=completion.system_health())


@app.get("/api/system/release-readiness")
def api_system_release_readiness():
    """Version 18 operator readiness checklist.

    This is intentionally file/runtime based so the UI can show whether the
    installed package includes the professional polish pieces we now expect in
    every release: progress everywhere, database safety, navigation, downloader
    monitoring, docs, and local GitHub release automation.
    """
    def exists(rel):
        return (BASE / rel).exists()
    checks = [
        {"key": "progress_everywhere", "label": "Progress everywhere", "ok": exists("docs/PROGRESS_EVERYWHERE_AND_LOGS.md") and exists("static/jobs.js") and exists("job_center.py"), "href": "/jobs"},
        {"key": "operations_progress", "label": "Operations scan progress", "ok": exists("docs/RELEASE_NOTES_v17.22.0.md") and exists("static/operations.js"), "href": "/operations"},
        {"key": "show_queue_sort", "label": "Show Queue sort accuracy", "ok": exists("docs/RELEASE_NOTES_v17.23.0.md") and exists("static/show_queue.js"), "href": "/show-queue"},
        {"key": "download_center", "label": "Downloader validation center", "ok": exists("docs/DOWNLOADER_VALIDATION_CENTER.md") and exists("static/download_center.js"), "href": "/download-center"},
        {"key": "database_safety", "label": "Database safety guard", "ok": exists("docs/DATABASE_PROTECTION_CENTER.md") and exists("database_safety.py") and exists("db_doctor.py"), "href": "/database-safety"},
        {"key": "media_maintenance", "label": "Media server maintenance", "ok": exists("docs/RELEASE_NOTES_v17.20.0.md") and exists("templates/settings.html"), "href": "/settings"},
        {"key": "release_push", "label": "Local GitHub release automation", "ok": exists("release-and-push.ps1") and exists("docs/GITHUB_RELEASE_AUTOMATION.md"), "href": "/about"},
        {"key": "v18_docs", "label": "Version 18 documentation", "ok": exists("docs/RELEASE_NOTES_v18.0.0.md") and exists("docs/VERSION_18_READINESS.md"), "href": "/about"},
    ]
    passed = len([c for c in checks if c.get("ok")])
    total = len(checks)
    return jsonify(ok=True, version=APP_VERSION, label="Version 18 readiness", score=round((passed/total)*100) if total else 0, passed=passed, total=total, checks=checks)

@app.get("/api/docs")
def api_docs(): return jsonify(completion.api_summary())

@app.get("/api/retention/<int:pid>/preview")
def api_retention_preview(pid):
    try:return jsonify(completion.retention_preview(pid))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/retention/<int:pid>/apply")
def api_retention_apply(pid):
    try:return jsonify(completion.retention_apply(pid))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/episodes/<int:eid>/watched")
def api_episode_watched(eid):
    body=request.get_json(silent=True) or {}
    completion.set_watched(eid,body.get("percent",100),body.get("profile","default"),body.get("source","manual"))
    return jsonify(ok=True)


@app.get("/upgrades")
def upgrades_page(): return render_template("upgrades.html")

@app.get("/api/upgrades")
def api_upgrades(): return jsonify(production.plan_upgrades())

@app.get("/api/subtitle-providers")
def api_subtitle_providers(): return jsonify(results=production.subtitle_providers())

@app.post("/api/subtitle-providers")
def api_subtitle_provider_save():
    body=request.get_json(silent=True) or {}
    try:return jsonify(ok=True,id=production.save_subtitle_provider(body))
    except Exception as e:return jsonify(error=str(e)),400

@app.get("/api/episodes/<int:eid>/subtitle-search")
def api_episode_subtitle_search(eid):
    try:return jsonify(production.search_subtitles(eid))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/episodes/<int:eid>/subtitle-download")
def api_episode_subtitle_download(eid):
    body=request.get_json(silent=True) or {}
    try:return jsonify(production.download_subtitle(eid,body["provider"],body["file_id"],body.get("language","en")))
    except Exception as e:return jsonify(error=str(e)),400

@app.get("/api/season-packs/<int:sid>/<int:season>/search")
def api_season_pack_search(sid,season):
    try:return jsonify(production.season_pack_search(sid,season))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/backup/validate")
def api_backup_validate():
    body=request.get_json(silent=True) or {}
    try:return jsonify(production.validate_backup(body.get("path","")))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/diagnostics")
def api_diagnostics():
    try:return jsonify(production.diagnostic_bundle())
    except Exception as e:return jsonify(error=str(e)),400

@app.get("/api/diagnostics/download/<name>")
def api_diagnostics_download(name):
    safe=secure_filename(name);path=BASE/"diagnostics"/safe
    if not path.exists():return jsonify(error="Diagnostic bundle not found"),404
    return send_file(path,as_attachment=True,download_name=safe)


@app.post("/api/season-packs/grab/<int:search_id>")
def api_season_pack_grab(search_id):
    try:return jsonify(release.grab_season_pack(search_id))
    except Exception as e:return jsonify(error=str(e)),400

@app.get("/api/security/tokens")
def api_security_tokens(): return jsonify(results=release.api_tokens())

@app.post("/api/security/tokens")
def api_security_token_create():
    body=request.get_json(silent=True) or {}
    token=release.create_api_token(body.get("name","API Client"))
    return jsonify(ok=True,token=token,message="Copy this token now. It will not be shown again.")

@app.delete("/api/security/tokens/<int:tid>")
def api_security_token_revoke(tid):
    release.revoke_api_token(tid);return jsonify(ok=True)

@app.post("/api/media-servers/<int:sid>/sync-watched")
def api_sync_watched(sid):
    body=request.get_json(silent=True) or {}
    try:return jsonify(sync.sync_watched(sid,body.get("profile","default"),body.get("user_id")))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/media-servers/<int:sid>/sync-watched/start")
def api_sync_watched_start(sid):
    body=request.get_json(silent=True) or {}
    profile=body.get("profile","default")
    user_id=body.get("user_id")
    def worker(job_id):
        server=advanced.media_server(sid)
        job_center.update_job(job_id, stage="Watched sync", message=f"Syncing watched state from {server.get('name')}.", percent=20, total=1)
        result=sync.sync_watched(sid,profile,user_id)
        job_center.update_job(job_id, status="complete", stage="Complete", message=f"Watched sync complete for {server.get('name')}.", percent=100, processed=1, succeeded=1, total=1, result=result)
        return result
    return jsonify(ok=True, job=job_center.run_background("media_server_watched_sync", worker, stage="Queued", message="Watched sync queued.", meta={"media_server_id":sid,"profile":profile}))

@app.post("/api/subtitles/jobs/enqueue")
def api_subtitle_jobs_enqueue():
    body=request.get_json(silent=True) or {}
    return jsonify(ok=True,queued=sync.enqueue_missing_subtitles(body.get("language","en")))

@app.post("/api/subtitles/jobs/run")
def api_subtitle_jobs_run():
    body=request.get_json(silent=True) or {}
    return jsonify(sync.run_subtitle_jobs(body.get("limit",20)))

@app.post("/api/subtitles/jobs/run/start")
def api_subtitle_jobs_run_start():
    body=request.get_json(silent=True) or {}
    limit=max(1,min(200,int(body.get("limit",20))))
    def worker(job_id):
        job_center.update_job(job_id, stage="Subtitle jobs", message=f"Running up to {limit} subtitle jobs.", percent=10, total=limit)
        result=sync.run_subtitle_jobs(limit)
        completed=int(result.get("completed",0) or 0)
        failed=int(result.get("failed",0) or 0)
        job_center.update_job(job_id, status="complete", stage="Subtitle jobs complete", message=f"Subtitle jobs complete: {completed} completed, {failed} failed.", percent=100, result=result, processed=completed+failed, succeeded=completed, failed=failed, total=max(limit,completed+failed))
        return result
    return jsonify(ok=True, job=job_center.run_background("subtitle_jobs", worker, stage="Queued", message="Subtitle job runner queued.", meta={"limit":limit}))

@app.get("/api/upgrades/propers")
def api_proper_candidates(): return jsonify(results=sync.proper_repack_candidates())

@app.get("/api/mapping-sources")
def api_mapping_sources(): return jsonify(results=sync.mapping_status())

@app.post("/api/mapping-sources")
def api_mapping_source_save():
    body=request.get_json(silent=True) or {}
    sync.save_mapping_source(body.get("name","Mapping Source"),body.get("kind","xem"),body.get("base_url",""),body.get("enabled",True))
    return jsonify(ok=True)


@app.post("/api/upgrades/propers/<int:episode_id>/search")
def api_proper_repack_search(episode_id):
    body=request.get_json(silent=True) or {}
    try:return jsonify(sync.proper_repack_search(episode_id,bool(body.get("grab",False))))
    except Exception as e:return jsonify(error=str(e)),400

@app.get("/api/scheduler/runs")
def api_scheduler_runs():
    with cx() as c:
        rows=c.execute("SELECT * FROM scheduler_runs ORDER BY id DESC LIMIT 200").fetchall()
    return jsonify(results=[dict(r) for r in rows])

@app.get("/api/season-packs/downloads")
def api_season_pack_downloads():
    with cx() as c:
        rows=c.execute("""SELECT p.*,s.name show_name,
                          (SELECT COUNT(*) FROM acquisition_episode_links l
                           WHERE l.acquisition_type='season_pack' AND l.acquisition_id=p.id) episode_count
                          FROM season_pack_downloads p JOIN shows s ON s.id=p.show_id
                          ORDER BY p.id DESC LIMIT 200""").fetchall()
    return jsonify(results=[dict(r) for r in rows])


@app.get("/api/queue/unified")
def api_queue_unified():
    return jsonify(results=lifecycle.unified_queue())

@app.get("/api/acquisitions/<kind>/<int:acquisition_id>/events")
def api_acquisition_events(kind,acquisition_id):
    with cx() as c:
        rows=c.execute("""SELECT * FROM acquisition_events
                          WHERE acquisition_type=? AND acquisition_id=?
                          ORDER BY id DESC LIMIT 200""",(kind,acquisition_id)).fetchall()
    return jsonify(results=[dict(r) for r in rows])


@app.get("/api/upgrades/replacements")
def api_upgrade_replacements():
    with cx() as c:
        rows=c.execute("""SELECT u.*,s.name show_name,e.season,e.episode
                          FROM upgrade_replacements u
                          JOIN episodes e ON e.id=u.episode_id
                          JOIN shows s ON s.id=e.show_id
                          ORDER BY u.id DESC LIMIT 200""").fetchall()
    return jsonify(results=[dict(r) for r in rows])

@app.post("/api/upgrades/replacements/<int:replacement_id>/rollback")
def api_upgrade_rollback(replacement_id):
    try:return jsonify(lifecycle.rollback_replacement(replacement_id))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/media-servers/<int:sid>/refresh-target")
def api_media_refresh_target(sid):
    body=request.get_json(silent=True) or {}
    try:return jsonify(advanced.refresh_media_server_target(sid,body.get("path"),body.get("show_id")))
    except Exception as e:return jsonify(error=str(e)),400



@app.get("/api/naming/config")
def api_naming_config():
    pattern=engine.get_setting("General","naming_pattern","Season %0S/%SN - S%0SE%0E - %EN")
    rename_enabled=engine.as_bool(engine.get_setting("General","rename_episodes","1"),True)
    move_associated=engine.as_bool(engine.get_setting("General","move_associated_files","1"),True)
    presets=[
        {"name":"SickChill Default","pattern":"Season %0S/%SN - S%0SE%0E - %EN"},
        {"name":"Compact","pattern":"Season %0S/S%0SE%0E - %EN"},
        {"name":"Show + Episode","pattern":"%SN/Season %0S/%SN - S%0SE%0E - %EN"},
        {"name":"Scene Style","pattern":"%SN.S%0SE%0E.%EN"},
    ]
    sample=[{"season":1,"episode":1,"name":"Pilot"},{"season":1,"episode":2,"name":"Second Episode"}]
    preview=str(naming.render(pattern,"Example Show",sample,".mkv")).replace("\\","/")
    return jsonify(pattern=pattern,rename_episodes=rename_enabled,move_associated_files=move_associated,
                   presets=presets,preview=preview)

@app.post("/api/naming/config")
def api_naming_config_save():
    body=request.get_json(silent=True) or {}
    pattern=str(body.get("pattern") or "").strip()
    if not pattern:return jsonify(error="Naming pattern is required"),400
    try:
        sample=[{"season":1,"episode":1,"name":"Pilot"},{"season":1,"episode":2,"name":"Second Episode"}]
        preview=str(naming.render(pattern,"Example Show",sample,".mkv")).replace("\\","/")
        engine.set_setting("General","naming_pattern",pattern,source="tvmanager")
        engine.set_setting("General","rename_episodes","1" if body.get("rename_episodes",True) else "0",source="tvmanager")
        engine.set_setting("General","move_associated_files","1" if body.get("move_associated_files",True) else "0",source="tvmanager")
        return jsonify(ok=True,preview=preview)
    except Exception as ex:
        return jsonify(error=str(ex)),400

@app.post("/api/naming/preview-sample")
def api_naming_preview_sample():
    body=request.get_json(silent=True) or {}
    pattern=str(body.get("pattern") or "Season %0S/%SN - S%0SE%0E - %EN")
    try:
        sample=[{"season":1,"episode":1,"name":"Pilot"},{"season":1,"episode":2,"name":"Second Episode"}]
        return jsonify(preview=str(naming.render(pattern,"Example Show",sample,".mkv")).replace("\\","/"))
    except Exception as ex:
        return jsonify(error=str(ex)),400

@app.get("/api/naming/preview/<int:episode_id>")
def api_naming_preview(episode_id):
    with cx() as c:
        e=c.execute("""SELECT e.*,s.name show_name,s.location show_location,s.season_folders
                       FROM episodes e JOIN shows s ON s.id=e.show_id WHERE e.id=?""",(episode_id,)).fetchone()
        if not e:return jsonify(error="Episode not found"),404
        pat=c.execute("""SELECT value FROM settings WHERE lower(section)='general'
                         AND lower(name)='naming_pattern'""").fetchone()
        ren=c.execute("""SELECT value FROM settings WHERE lower(section)='general'
                         AND lower(name)='rename_episodes'""").fetchone()
    pattern=pat["value"] if pat and pat["value"] else "Season %0S/%SN - S%0SE%0E - %EN"
    rename=str(ren["value"] if ren else "1").lower() in {"1","true","yes","on"}
    dest=naming.configured_destination(e["show_location"] or ".",e["show_name"],[dict(e)],
                                       e["location"] or "episode.mkv",pattern,rename,bool(e["season_folders"]))
    return jsonify(pattern=pattern,rename=rename,destination=str(dest))

@app.get("/api/library/fingerprint-conflicts")
def api_fingerprint_conflicts():
    limit=request.args.get("limit","500")
    try:groups=integrity.duplicate_content(int(limit))
    except Exception as e:return jsonify(error=str(e)),400
    return jsonify(groups=groups,count=len(groups))

@app.post("/api/library/fingerprint-conflicts/start")
def api_fingerprint_conflicts_start():
    body=request.get_json(silent=True) or {}
    try:
        limit=max(1,min(int(body.get("limit") or request.args.get("limit","500")),2000))
    except Exception:
        limit=500
    def worker(job_id):
        job_center.update_job(job_id, stage="Content fingerprint scan", message="Scanning cached fingerprints for duplicate media content.", percent=20, total=limit)
        groups=integrity.duplicate_content(limit)
        duplicate_files=sum(len(g) for g in groups)
        job_center.update_job(job_id, status="complete", stage="Fingerprint scan complete", message=f"Found {len(groups)} duplicate content groups.", percent=100, result={"groups":groups,"count":len(groups)}, processed=duplicate_files, failed=len(groups), total=limit)
        return {"groups":groups,"count":len(groups)}
    return jsonify(ok=True, job=job_center.run_background("content_fingerprint_scan", worker, stage="Queued", message="Content duplicate fingerprint scan queued.", meta={"limit":limit}))


@app.get("/api/scheduler/leases")
def api_scheduler_leases():
    return jsonify(results=scheduler_guard.leases())

@app.get("/api/import/history")
def hist():
    with cx() as c: rows=c.execute("SELECT * FROM import_runs ORDER BY id DESC LIMIT 20").fetchall()
    return jsonify(results=[dict(r) for r in rows])

backup_before_upgrade()
init()
engine.init_engine()
__import__("notifiers").init()
__import__("scene_sync").init()
sickchill_parity.init(DB)
migrations.migrate(DB)
lifecycle.init()
integrity.init()
scheduler_guard.init()
security.init()
metadata_service.init()
engine.normalize_statuses()

if __name__=="__main__":
    engine.start_scheduler()
    app.run(host="127.0.0.1",port=int(os.getenv("PORT","5050")),debug=False,use_reloader=False,threaded=True)
