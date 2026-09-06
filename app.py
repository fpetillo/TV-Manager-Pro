import dbcore
import migrations
import lifecycle
import naming
import integrity
import scheduler_guard
import security
import metadata_service
import sickchill_importer
import library_maintenance
import configparser, json, os, shutil, sqlite3, io, zipfile
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

BASE=Path(__file__).resolve().parent
load_dotenv(BASE/".env")
DB=BASE/"tvmanager.db"
IMPORTS=BASE/"imports"; IMPORTS.mkdir(exist_ok=True)
TMDB=os.getenv("TMDB_BEARER_TOKEN","").strip()
app=Flask(__name__)
app.secret_key=security.session_secret()
app.config["MAX_CONTENT_LENGTH"]=512*1024*1024
app.config["SESSION_COOKIE_HTTPONLY"]=True
app.config["SESSION_COOKIE_SAMESITE"]="Lax"
app.config["SESSION_COOKIE_SECURE"]=str(os.getenv("TVMANAGER_HTTPS","0")).lower() in {"1","true","yes","on"}

BACKUPS=BASE/"backups"; BACKUPS.mkdir(exist_ok=True)
MANAGED_TRASH=BASE/"managed_trash"; MANAGED_TRASH.mkdir(exist_ok=True)

def backup_before_upgrade():
    if not DB.exists():
        return None
    marker=BACKUPS/"v4.1-backup.done"
    if marker.exists():
        return None
    stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
    target=BACKUPS/f"tvmanager-before-v4.1-{stamp}.db"
    shutil.copy2(DB,target)
    marker.write_text(target.name,encoding="utf-8")
    return target


def cx(path=None):
    return dbcore.connect(path or DB,wal=(path is None))

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
            "tvdb_id": "INTEGER",
            "legacy_indexer_id": "INTEGER",
            "location": "TEXT",
            "network": "TEXT",
            "genre": "TEXT",
            "quality": "TEXT",
            "paused": "INTEGER DEFAULT 0",
            "anime": "INTEGER DEFAULT 0",
            "legacy_data": "TEXT",
        })

        _ensure_columns(c, "episodes", {
            "file_size": "INTEGER",
            "release_name": "TEXT",
            "quality": "TEXT",
            "legacy_data": "TEXT",
        })

        # Older v2 databases may still have tmdb_id defined NOT NULL.
        # Rebuild the table once so SickChill shows without TMDb IDs can import.
        if _shows_tmdb_is_not_null(c):
            _rebuild_shows_nullable_tmdb(c)

        c.execute("CREATE INDEX IF NOT EXISTS idx_shows_imdb ON shows(imdb_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_shows_tvdb ON shows(tvdb_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_shows_legacy ON shows(legacy_indexer_id)")

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
    if not TMDB: raise RuntimeError("TMDB_BEARER_TOKEN is not configured in .env")
    r=requests.get("https://api.themoviedb.org/3"+path,headers={"Authorization":"Bearer "+TMDB,"accept":"application/json"},params=params or {},timeout=15); r.raise_for_status(); return r.json()


PUBLIC_PATHS={"/login","/api/health","/api/security/status"}

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
@app.get("/manager")
def manager(): return render_template("manager.html")
@app.get("/library-health")
def library_health_page(): return render_template("library_health.html")
@app.get("/import")
def importer(): return render_template("import.html")

@app.get("/api/search")
def search():
    q=(request.args.get("q") or "").strip()
    if not q:return jsonify(error="Enter a TV show name."),400
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
    except Exception as e:return jsonify(error=str(e)),500

@app.get("/api/shows")
def shows():
    q=(request.args.get("q") or "").strip()
    status=(request.args.get("status") or "").strip()
    group_id=(request.args.get("group_id") or "").strip()
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
    sql="""SELECT s.*,
                  (SELECT COUNT(*) FROM episodes e WHERE e.show_id=s.id) episode_count,
                  (SELECT COUNT(DISTINCT season) FROM episodes e WHERE e.show_id=s.id) season_count
           FROM shows s"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY s.name COLLATE NOCASE"
    with cx() as c:
        rows=c.execute(sql,params).fetchall()
    return jsonify(results=[dict(r) for r in rows])


@app.get("/api/shows/<int:sid>/episodes")
def eps(sid):
    season=request.args.get("season")
    with cx() as c:
        show=c.execute("SELECT * FROM shows WHERE id=?",(sid,)).fetchone()
        if not show:
            return jsonify(error="Show not found"),404
        if season is None:
            rows=c.execute("""
                SELECT season, COUNT(*) AS episode_count,
                       SUM(CASE WHEN location IS NOT NULL AND TRIM(location)<>'' THEN 1 ELSE 0 END) AS with_files
                FROM episodes
                WHERE show_id=?
                GROUP BY season
                ORDER BY season
            """,(sid,)).fetchall()
            return jsonify(show=dict(show),seasons=[dict(r) for r in rows])
        rows=c.execute("""
            SELECT * FROM episodes
            WHERE show_id=? AND season=?
            ORDER BY episode
        """,(sid,int(season))).fetchall()
    return jsonify(show=dict(show),season=int(season),episodes=[dict(r) for r in rows])

@app.get("/api/shows/<int:sid>")
def show_detail(sid):
    with cx() as c:
        show=c.execute("""
            SELECT s.*,
                   (SELECT COUNT(*) FROM episodes e WHERE e.show_id=s.id) AS episode_count,
                   (SELECT COUNT(DISTINCT season) FROM episodes e WHERE e.show_id=s.id) AS season_count
            FROM shows s WHERE s.id=?
        """,(sid,)).fetchone()
        if not show:
            return jsonify(error="Show not found"),404
    return jsonify(show=dict(show))


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

@app.post("/api/shows/<int:sid>/refresh")
def refresh_show_metadata(sid):
    with cx() as c:
        show=c.execute("SELECT * FROM shows WHERE id=?",(sid,)).fetchone()
    if not show:
        return jsonify(error="Show not found"),404
    try:
        tmdb_id=resolve_tmdb_show(show)
        if not tmdb_id:
            return jsonify(error="Could not match this imported show to TMDb using its current IMDb/TVDb IDs."),404

        info=tmdb(f"/tv/{tmdb_id}",{"language":"en-US","append_to_response":"external_ids"})
        ext=info.get("external_ids") or {}
        poster_path=info.get("poster_path")
        genres=", ".join(x.get("name","") for x in info.get("genres",[]) if x.get("name"))
        networks=", ".join(x.get("name","") for x in info.get("networks",[]) if x.get("name"))

        inserted=0
        updated=0
        with cx() as c:
            c.execute("""UPDATE shows SET
                tmdb_id=?, imdb_id=COALESCE(NULLIF(?,''),imdb_id),
                tvdb_id=COALESCE(?,tvdb_id), name=?, original_name=?,
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
                    sd=tmdb(f"/tv/{tmdb_id}/season/{sn}",{"language":"en-US"})
                except Exception:
                    continue
                for ep in sd.get("episodes",[]):
                    en=ep.get("episode_number")
                    if en is None:
                        continue
                    existing=c.execute("SELECT id,location,status FROM episodes WHERE show_id=? AND season=? AND episode=?",
                                       (sid,sn,en)).fetchone()
                    air=ep.get("air_date")
                    default_status="Unaired" if air and air>today else "Wanted"
                    if existing:
                        c.execute("""UPDATE episodes SET
                            name=COALESCE(NULLIF(?,''),name),
                            airdate=COALESCE(NULLIF(?,''),airdate)
                            WHERE id=?""",(ep.get("name"),air,existing["id"]))
                        updated+=1
                    else:
                        c.execute("""INSERT INTO episodes(show_id,season,episode,name,airdate,status)
                                     VALUES(?,?,?,?,?,?)""",(sid,sn,en,ep.get("name"),air,default_status))
                        inserted+=1
            c.commit()
        return jsonify(ok=True,tmdb_id=tmdb_id,episodes_inserted=inserted,episodes_updated=updated,
                       message=f"Metadata refreshed. {inserted} episodes added and {updated} existing episodes updated.")
    except Exception as e:
        return jsonify(error=str(e)),500

@app.get("/api/dashboard")
def dashboard():
    with cx() as c:
        shows=c.execute("SELECT COUNT(*) c FROM shows").fetchone()["c"]
        episodes=c.execute("SELECT COUNT(*) c FROM episodes").fetchone()["c"]
        downloaded=c.execute("SELECT COUNT(*) c FROM episodes WHERE location IS NOT NULL AND TRIM(location)<>''").fetchone()["c"]
        wanted=c.execute("""SELECT COUNT(*) c FROM episodes
                            WHERE (location IS NULL OR TRIM(location)='')
                              AND lower(COALESCE(status,'')) IN ('wanted','failed')""").fetchone()["c"]
    return jsonify(shows=shows,episodes=episodes,downloaded=downloaded,wanted=wanted)

@app.post("/api/shows")
def add():
    x=request.get_json() or {}; name=(x.get("name") or "").strip()
    with cx() as c:
        if existing(c,tmdb=x.get("tmdb_id"),imdb=x.get("imdb_id"),name=name):return jsonify(ok=True,message=f"{name} is already in TV Manager.")
        c.execute("""INSERT INTO shows(tmdb_id,imdb_id,name,original_name,first_air_date,overview,poster,vote_average,status)
                   VALUES(?,?,?,?,?,?,?,?,?)""",(x.get("tmdb_id"),x.get("imdb_id"),name,x.get("original_name"),x.get("first_air_date"),x.get("overview"),x.get("poster"),x.get("vote_average"),"Wanted"))
    return jsonify(ok=True,message=f"{name} added to TV Manager."),201

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

@app.post("/api/import/sickchill")
def doimport():
    name,dest,error=_save_sickchill_upload()
    if error:return error
    try:
        st=sickchill_importer.import_database(dest,DB,name,dry_run=False)
        st["backup"]=Path(str(dest)+".backup").name
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

@app.get("/api/settings")
def settings_api():
    return jsonify(results=get_settings_grouped())



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

@app.get("/settings")
def settings_page(): return render_template("settings.html")

@app.get("/postprocess")
def postprocess_page(): return render_template("postprocess.html")

@app.get("/api/upcoming")
def api_upcoming():
    return jsonify(results=engine.upcoming(max(1,min(90,int(request.args.get("days","14"))))))

@app.get("/api/missing")
def api_missing():
    return jsonify(results=engine.missing(max(1,min(2000,int(request.args.get("limit","500"))))))

@app.get("/api/activity")
def api_activity():
    return jsonify(results=engine.activity(max(1,min(1000,int(request.args.get("limit","200"))))))

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

@app.post("/api/episodes/<int:eid>/search")
def api_episode_search(eid):
    body=request.get_json(silent=True) or {}
    try:
        return jsonify(engine.search_episode(eid,auto_grab=bool(body.get("auto_grab",False))))
    except Exception as e:
        return jsonify(error=str(e)),400

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
    return jsonify(engine.run_job(name))

@app.post("/api/settings/tvmanager")
def api_tvmanager_settings():
    body=request.get_json(silent=True) or {}
    allowed={"auto_grab","recent_days","max_searches_per_run","refresh_media_servers_after_process","simulation_mode","api_auth_enabled"}
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
    if not fields:
        return jsonify(error="Nothing to update"),400
    vals.append(eid)
    with cx() as c:
        c.execute("UPDATE episodes SET "+",".join(fields)+" WHERE id=?",vals)
        c.commit()
    return jsonify(ok=True)

@app.patch("/api/shows/<int:sid>/options")
def api_show_options(sid):
    body=request.get_json(silent=True) or {}
    allowed={"paused","monitor_new","search_enabled","preferred_words","required_words","ignored_words",
             "season_folders","scene_numbering","air_by_date","sports","metadata_enabled","quality_profile_id","favorite","retention_policy_id"}
    fields=[]; vals=[]
    for k,v in body.items():
        if k not in allowed: continue
        fields.append(f"{k}=?")
        vals.append((1 if v else 0) if k in {"paused","monitor_new","search_enabled","season_folders","scene_numbering","air_by_date","sports","metadata_enabled","quality_profile_id","favorite","retention_policy_id"} else v)
    if not fields:
        return jsonify(error="Nothing to update"),400
    vals.append(sid)
    with cx() as c:
        c.execute("UPDATE shows SET "+",".join(fields)+" WHERE id=?",vals);c.commit()
    return jsonify(ok=True)

@app.get("/api/postprocess/scan")
def api_postprocess_scan():
    return jsonify(engine.scan_postprocess(dry_run=True))

@app.post("/api/postprocess/run")
def api_postprocess_run():
    try:
        return jsonify(engine.scan_postprocess(dry_run=False))
    except Exception as e:
        return jsonify(error=str(e)),400


@app.get("/api/tvmanager/config")
def api_tvmanager_config():
    return jsonify(
        automation_enabled=engine.as_bool(engine.get_setting("TVManager","automation_enabled","0")),
        auto_grab=engine.as_bool(engine.get_setting("TVManager","auto_grab","1")),
        recent_days=engine.as_int(engine.get_setting("TVManager","recent_days","14"),14),
        max_searches_per_run=engine.as_int(engine.get_setting("TVManager","max_searches_per_run","25"),25),
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

@app.post("/api/shows/<int:sid>/scan-library")
def api_scan_show_library(sid):
    with cx() as c:
        show=c.execute("SELECT * FROM shows WHERE id=?",(sid,)).fetchone()
    if not show:
        return jsonify(error="Show not found"),404
    root=show["location"]
    if not root:
        return jsonify(error="This show has no library folder configured."),400
    from pathlib import Path
    p=Path(root)
    if not p.exists():
        return jsonify(error="The configured show folder is not reachable from this computer."),400
    matched=0;files=0;unmatched=[]
    media={".mkv",".mp4",".avi",".m4v",".mov",".ts",".mpeg",".mpg",".wmv"}
    for f in p.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in media:
            continue
        files+=1
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
    return jsonify(ok=True,files=files,matched=matched,unmatched=unmatched)

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
    return jsonify(ok=True,id=advanced.save_group(body.get("name","New Group"),body.get("show_ids")))

@app.get("/api/groups/<int:gid>/shows")
def api_group_shows(gid): return jsonify(results=advanced.group_shows(gid))

@app.get("/api/webhooks")
def api_webhooks(): return jsonify(results=advanced.webhooks())

@app.post("/api/webhooks")
def api_webhook_save():
    body=request.get_json(silent=True) or {}
    try:return jsonify(ok=True,id=advanced.save_webhook(body))
    except Exception as e:return jsonify(error=str(e)),400

@app.get("/api/media-servers")
def api_media_servers(): return jsonify(results=advanced.media_servers())

@app.post("/api/media-servers")
def api_media_server_save():
    body=request.get_json(silent=True) or {}
    try:return jsonify(ok=True,id=advanced.save_media_server(body))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/media-servers/<int:sid>/test")
def api_media_server_test(sid):
    try:return jsonify(advanced.test_media_server(sid))
    except Exception as e:return jsonify(error=str(e)),400

@app.post("/api/media-servers/<int:sid>/refresh")
def api_media_server_refresh(sid):
    try:return jsonify(advanced.refresh_media_server(sid))
    except Exception as e:return jsonify(error=str(e)),400

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

@app.get("/api/library/conflicts")
def api_library_conflicts(): return jsonify(results=ops.detect_conflicts())

@app.get("/api/library/duplicates")
def api_library_duplicates_v17():
    try:
        limit=int(request.args.get("limit",100))
    except Exception:
        limit=100
    return jsonify(results=library_maintenance.duplicate_candidates(DB,limit=max(1,min(limit,500))))

@app.get("/api/library/health-report")
def api_library_health_report_v171():
    try:
        duplicate_limit=int(request.args.get("duplicate_limit",25))
        sample_limit=int(request.args.get("sample_limit",25))
    except Exception:
        duplicate_limit=25; sample_limit=25
    return jsonify(library_maintenance.library_health_report(DB,duplicate_limit=max(1,min(duplicate_limit,100)),sample_limit=max(1,min(sample_limit,100))))

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

@app.post("/api/metadata/refresh/run")
def api_metadata_refresh_run():
    body=request.get_json(silent=True) or {}
    batch_size=int(body.get("batch_size") or 5)
    return jsonify(ok=True,**metadata_service.refresh_batch(batch_size=max(1,min(batch_size,50))))


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
    return jsonify(ok=True,id=intelligence.save_tag(body.get("name","Tag"),body.get("color","slate")))

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

@app.post("/api/subtitles/jobs/enqueue")
def api_subtitle_jobs_enqueue():
    body=request.get_json(silent=True) or {}
    return jsonify(ok=True,queued=sync.enqueue_missing_subtitles(body.get("language","en")))

@app.post("/api/subtitles/jobs/run")
def api_subtitle_jobs_run():
    body=request.get_json(silent=True) or {}
    return jsonify(sync.run_subtitle_jobs(body.get("limit",20)))

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
migrations.migrate(DB)
lifecycle.init()
integrity.init()
scheduler_guard.init()
security.init()
metadata_service.init()
engine.normalize_statuses()

if __name__=="__main__":
    engine.start_scheduler()
    app.run(host="127.0.0.1",port=int(os.getenv("PORT","5050")),debug=True,use_reloader=False)
