from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import os, socket, uuid
import dbcore

BASE=Path(__file__).resolve().parent
DB=BASE/"tvmanager.db"
OWNER=f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"

def cx():
    return dbcore.connect(DB)

def init():
    with cx() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS scheduler_runs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,job_name TEXT NOT NULL,
          started_at TEXT DEFAULT CURRENT_TIMESTAMP,finished_at TEXT,
          status TEXT DEFAULT 'Running',message TEXT
        );
        CREATE TABLE IF NOT EXISTS scheduler_leases(
          job_name TEXT PRIMARY KEY,
          owner TEXT NOT NULL,
          acquired_at TEXT NOT NULL,
          expires_at TEXT NOT NULL
        );
        """)
        c.execute("DELETE FROM scheduler_leases WHERE expires_at<=CURRENT_TIMESTAMP")
        c.execute("""UPDATE scheduler_runs SET status='Abandoned',finished_at=CURRENT_TIMESTAMP,
                     message=COALESCE(message,'') || ' [Recovered after restart]'
                     WHERE status='Running' AND finished_at IS NULL
                     AND NOT EXISTS (
                       SELECT 1 FROM scheduler_leases l
                       WHERE l.job_name=scheduler_runs.job_name AND l.expires_at>CURRENT_TIMESTAMP
                     )""")
        c.commit()

def acquire(job_name,lease_minutes=30):
    now=datetime.now()
    expires=now+timedelta(minutes=max(5,int(lease_minutes)))
    with cx() as c:
        c.execute("DELETE FROM scheduler_leases WHERE expires_at<=CURRENT_TIMESTAMP")
        existing=c.execute("SELECT * FROM scheduler_leases WHERE job_name=?",(job_name,)).fetchone()
        if existing:return False
        try:
            c.execute("""INSERT INTO scheduler_leases(job_name,owner,acquired_at,expires_at)
                         VALUES(?,?,?,?)""",(job_name,OWNER,now.strftime("%Y-%m-%d %H:%M:%S"),expires.strftime("%Y-%m-%d %H:%M:%S")))
            c.commit();return True
        except Exception:
            c.rollback();return False

def renew(job_name,lease_minutes=15):
    now=datetime.now()
    expires=now+timedelta(minutes=max(5,int(lease_minutes)))
    with cx() as c:
        cur=c.execute("""UPDATE scheduler_leases SET expires_at=?
                         WHERE job_name=? AND owner=?""",
                      (expires.strftime("%Y-%m-%d %H:%M:%S"),job_name,OWNER))
        c.commit()
        return cur.rowcount==1


def release(job_name):
    with cx() as c:
        c.execute("DELETE FROM scheduler_leases WHERE job_name=? AND owner=?",(job_name,OWNER));c.commit()

def leases():
    with cx() as c:return [dict(r) for r in c.execute("SELECT * FROM scheduler_leases ORDER BY job_name").fetchall()]
