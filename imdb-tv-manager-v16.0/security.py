from __future__ import annotations
from pathlib import Path
from datetime import datetime
import base64
import hashlib
import hmac
import os
import secrets
import dbcore

BASE=Path(__file__).resolve().parent
DB=BASE/"tvmanager.db"
SECRET_FILE=BASE/".tvmanager-session-key"
PBKDF2_ITERATIONS=350_000

def cx():
    return dbcore.connect(DB)

def init():
    with cx() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS admin_users(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL,
          salt TEXT NOT NULL,
          iterations INTEGER NOT NULL,
          enabled INTEGER DEFAULT 1,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          last_login TEXT
        );
        CREATE TABLE IF NOT EXISTS login_attempts(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT,
          remote_addr TEXT,
          success INTEGER DEFAULT 0,
          attempted_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_login_attempts_addr
          ON login_attempts(remote_addr,attempted_at);
        CREATE TABLE IF NOT EXISTS security_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          event_type TEXT NOT NULL,
          username TEXT,
          remote_addr TEXT,
          detail TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        c.commit()

def session_secret():
    env=os.getenv("TVMANAGER_SESSION_SECRET","").strip()
    if env:
        return env
    if SECRET_FILE.exists():
        value=SECRET_FILE.read_text(encoding="utf-8").strip()
        if len(value)>=32:
            return value
    value=secrets.token_urlsafe(48)
    SECRET_FILE.write_text(value,encoding="utf-8")
    try:
        os.chmod(SECRET_FILE,0o600)
    except OSError:
        pass
    return value

def _setting(name,default="0"):
    with cx() as c:
        r=c.execute("""SELECT value FROM settings
                       WHERE lower(section)='tvmanager' AND lower(name)=lower(?)""",(name,)).fetchone()
    return default if not r else r["value"]

def _set_setting(name,value):
    with cx() as c:
        c.execute("""INSERT INTO settings(section,name,value,is_secret,source,updated_at)
                     VALUES('TVManager',?,?,0,'tvmanager',CURRENT_TIMESTAMP)
                     ON CONFLICT(section,name) DO UPDATE SET
                       value=excluded.value,source='tvmanager',updated_at=CURRENT_TIMESTAMP""",
                  (name,str(value)))
        c.commit()

def as_bool(value):
    return str(value or "").strip().lower() in {"1","true","yes","on","enabled"}

def browser_auth_enabled():
    return as_bool(_setting("browser_auth_enabled","0"))

def set_browser_auth(enabled):
    if enabled and not admin_configured():
        raise ValueError("Create an administrator password before enabling browser authentication")
    _set_setting("browser_auth_enabled","1" if enabled else "0")

def admin_configured():
    with cx() as c:
        return c.execute("SELECT 1 FROM admin_users WHERE enabled=1 LIMIT 1").fetchone() is not None

def _derive(password,salt,iterations):
    raw=hashlib.pbkdf2_hmac("sha256",password.encode("utf-8"),salt,int(iterations))
    return base64.b64encode(raw).decode("ascii")

def validate_password(password):
    password=str(password or "")
    if len(password)<12:
        raise ValueError("Administrator password must be at least 12 characters")
    if len(password)>256:
        raise ValueError("Administrator password is too long")
    return password

def set_admin_password(username,password):
    username=(username or "admin").strip() or "admin"
    if len(username)>64:
        raise ValueError("Administrator username is too long")
    password=validate_password(password)
    salt=os.urandom(24)
    encoded_salt=base64.b64encode(salt).decode("ascii")
    digest=_derive(password,salt,PBKDF2_ITERATIONS)
    with cx() as c:
        c.execute("""INSERT INTO admin_users(username,password_hash,salt,iterations,enabled,updated_at)
                     VALUES(?,?,?,?,1,CURRENT_TIMESTAMP)
                     ON CONFLICT(username) DO UPDATE SET
                       password_hash=excluded.password_hash,salt=excluded.salt,
                       iterations=excluded.iterations,enabled=1,updated_at=CURRENT_TIMESTAMP""",
                  (username,digest,encoded_salt,PBKDF2_ITERATIONS))
        c.commit()
    event("admin_password_changed",username,None,"Administrator credentials updated")
    return username

def authenticate(username,password,remote_addr=None):
    username=(username or "").strip()
    remote_addr=remote_addr or ""
    if login_blocked(remote_addr):
        event("login_blocked",username,remote_addr,"Too many recent failed login attempts")
        return None,"Too many failed attempts. Try again later."
    with cx() as c:
        row=c.execute("""SELECT * FROM admin_users
                         WHERE lower(username)=lower(?) AND enabled=1 LIMIT 1""",(username,)).fetchone()
    ok=False
    if row:
        try:
            salt=base64.b64decode(row["salt"])
            candidate=_derive(password or "",salt,int(row["iterations"]))
            ok=hmac.compare_digest(candidate,row["password_hash"])
        except Exception:
            ok=False
    with cx() as c:
        c.execute("""INSERT INTO login_attempts(username,remote_addr,success)
                     VALUES(?,?,?)""",(username,remote_addr,1 if ok else 0))
        if ok:
            c.execute("UPDATE admin_users SET last_login=CURRENT_TIMESTAMP WHERE id=?",(row["id"],))
        c.commit()
    if ok:
        event("login_success",row["username"],remote_addr,"Browser login successful")
        return dict(row),None
    event("login_failure",username,remote_addr,"Invalid username or password")
    return None,"Invalid username or password"

def login_blocked(remote_addr):
    if not remote_addr:
        return False
    with cx() as c:
        r=c.execute("""SELECT COUNT(*) c FROM login_attempts
                       WHERE remote_addr=? AND success=0
                       AND attempted_at>=datetime(CURRENT_TIMESTAMP,'-15 minutes')""",(remote_addr,)).fetchone()
    return int(r["c"] or 0)>=5

def event(event_type,username=None,remote_addr=None,detail=None):
    try:
        with cx() as c:
            c.execute("""INSERT INTO security_events(event_type,username,remote_addr,detail)
                         VALUES(?,?,?,?)""",(event_type,username,remote_addr,detail))
            c.commit()
    except Exception:
        pass

def recent_events(limit=100):
    with cx() as c:
        return [dict(r) for r in c.execute("""SELECT * FROM security_events
                                              ORDER BY id DESC LIMIT ?""",(int(limit),)).fetchall()]

def is_loopback(addr):
    addr=(addr or "").split("%",1)[0].strip().lower()
    return addr in {"127.0.0.1","::1","localhost"} or addr.startswith("127.")

def csrf_value(session):
    token=session.get("csrf_token")
    if not token:
        token=secrets.token_urlsafe(32)
        session["csrf_token"]=token
    return token

def status():
    with cx() as c:
        user=c.execute("""SELECT username,created_at,updated_at,last_login
                          FROM admin_users WHERE enabled=1 ORDER BY id LIMIT 1""").fetchone()
    return {
        "browser_auth_enabled":browser_auth_enabled(),
        "admin_configured":bool(user),
        "admin":dict(user) if user else None,
    }
