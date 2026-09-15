"""Persist a downloader intent before network I/O and retain uncertain outcomes.

A timeout cannot prove that a remote downloader rejected a request. Never retry
an unresolved intent automatically; the operator reconciles it in Download Center.
"""
import json
import uuid
import dbcore
from pathlib import Path
from contextlib import contextmanager
import media_operations

@contextmanager
def active(database,token):
    folder=Path(database).parent/".acquisition-locks"/token
    folder.mkdir(parents=True,exist_ok=True)
    with media_operations.exclusive(folder):
        yield



def init(database):
    with dbcore.connect(database) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS acquisition_intents(
          id TEXT PRIMARY KEY,kind TEXT NOT NULL,payload TEXT NOT NULL,client TEXT NOT NULL,
          state TEXT NOT NULL,external_id TEXT,acquisition_id INTEGER,
          message TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS acquisition_reservations(
          episode_id INTEGER PRIMARY KEY,intent_id TEXT NOT NULL REFERENCES acquisition_intents(id));
        """)


def reserve(database,kind,payload,client,episode_ids,token=None):
    init(database)
    ids=sorted(set(int(e) for e in episode_ids))
    if not ids:raise ValueError('No eligible episodes remain for this download.')
    token=token or uuid.uuid4().hex
    with dbcore.connect(database) as c:
        c.execute('BEGIN IMMEDIATE')
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for eid in ids:
            if c.execute('SELECT 1 FROM acquisition_reservations WHERE episode_id=?',(eid,)).fetchone():
                raise ValueError('A previous handoff is unresolved. Check Download Center before sending again.')
            if c.execute("SELECT 1 FROM downloads WHERE episode_id=? AND lower(status) IN ('queued','downloading','downloaded','importing')",(eid,)).fetchone():
                raise ValueError('An episode already has an active download.')
            if 'season_pack_downloads' in tables and c.execute("""SELECT 1 FROM season_pack_downloads p JOIN episodes e ON e.show_id=p.show_id AND e.season=p.season WHERE e.id=? AND lower(p.status) IN ('queued','downloading','downloaded','importing')""",(eid,)).fetchone():
                raise ValueError('An active season pack already covers this episode.')
        c.execute('INSERT INTO acquisition_intents(id,kind,payload,client,state) VALUES(?,?,?,?,?)',(token,kind,json.dumps(dict(payload)),client,'sending'))
        c.executemany('INSERT INTO acquisition_reservations(episode_id,intent_id) VALUES(?,?)',[(e,token) for e in ids])
    return token


def finish(database,token,external_id,finalize):
    with dbcore.connect(database) as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT * FROM acquisition_intents WHERE id=?',(token,)).fetchone()
        if not row or row['state'] in {'recorded','not_sent'}:raise ValueError('This handoff has already been resolved.')
        result=finalize(c,json.loads(row['payload']),row['client'],external_id)
        aid=result.get('download_id',result.get('season_pack_download_id'))
        c.execute("UPDATE acquisition_intents SET state='recorded',external_id=?,acquisition_id=?,message='Recorded',updated_at=CURRENT_TIMESTAMP WHERE id=?",(external_id,aid,token))
        c.execute('DELETE FROM acquisition_reservations WHERE intent_id=?',(token,))
        return result


def submit(database,kind,payload,client,episode_ids,sender,finalize):
    token=uuid.uuid4().hex
    with active(database,token):
        reserve(database,kind,payload,client,episode_ids,token=token)
        return _submit_reserved(database,token,sender,finalize)


def _submit_reserved(database,token,sender,finalize):
    try:
        external=sender()
        # Save the remote receipt independently, before recording the library state.
        with dbcore.connect(database) as c:
            c.execute("UPDATE acquisition_intents SET state='accepted',external_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(str(external or ''),token))
        return finish(database,token,external,finalize)
    except Exception:
        with dbcore.connect(database) as c:
            c.execute("UPDATE acquisition_intents SET state=CASE WHEN state='accepted' THEN state ELSE 'uncertain' END,message='Check the downloader queue and history before resolving this handoff.',updated_at=CURRENT_TIMESTAMP WHERE id=?",(token,))
        raise ValueError('Download outcome requires review in Download Center. It will not be sent again automatically.') from None


def listing(database):
    init(database)
    with dbcore.connect(database,readonly=True) as c:
        rows=c.execute("SELECT * FROM acquisition_intents WHERE state NOT IN ('recorded','not_sent') ORDER BY created_at DESC LIMIT 200").fetchall()
    return [{'id':r['id'],'kind':r['kind'],'client':r['client'],'state':r['state'],
             'external_id':r['external_id'] or '', 'title':json.loads(r['payload']).get('title',''),
             'created_at':r['created_at'],'message':r['message']} for r in rows]


def not_sent(database,token):
    with dbcore.connect(database) as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT state FROM acquisition_intents WHERE id=?',(token,)).fetchone()
        if not row or row['state'] in {'recorded','not_sent'}:raise ValueError('This handoff has already been resolved.')
        c.execute("UPDATE acquisition_intents SET state='not_sent',message='Operator confirmed absent from client queue and history',updated_at=CURRENT_TIMESTAMP WHERE id=?",(token,))
        c.execute('DELETE FROM acquisition_reservations WHERE intent_id=?',(token,))


def resolve(database,token,action,external_id=''):
    if len(token)!=32 or any(c not in '0123456789abcdef' for c in token):raise ValueError('Invalid handoff ID')
    with active(database,token):
        return _resolve(database,token,action,external_id)


def _resolve(database,token,action,external_id=''):
    if action=='not_sent':not_sent(database,token);return {'ok':True}
    if action!='accepted':raise ValueError('Choose whether the downloader accepted the release.')
    with dbcore.connect(database,readonly=True) as c:row=c.execute('SELECT * FROM acquisition_intents WHERE id=?',(token,)).fetchone()
    if not row:raise ValueError('Handoff not found')
    external=str(external_id or row['external_id'] or '').strip()
    if not external:raise ValueError('Enter the download ID from the client queue or history.')
    if row['kind']=='episode':
        from engine import record_episode_handoff as finalize
    else:
        from release import record_pack_handoff as finalize
    return finish(database,token,external,finalize)
