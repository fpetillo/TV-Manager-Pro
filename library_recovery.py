"""Reviewed, restart-time restore with a durable rollback journal."""
from pathlib import Path
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import sqlite3
import uuid
import zipfile
import stat
import threading
from functools import wraps
import media_operations

_LOCK=threading.RLock()

def serialized(fn):
    @wraps(fn)
    def guarded(base,*args,**kwargs):
        folder=Path(base)/"recovery";folder.mkdir(exist_ok=True)
        with _LOCK,media_operations.exclusive(folder):
            return fn(base,*args,**kwargs)
    return guarded

CORE = {'shows': {'id','name'}, 'episodes': {'id','show_id','season','episode'},
        'settings': {'section','name','value'}}
CONFIG = ('.env','config.ini','settings.ini','sickbeard.ini')
DATABASE_FILES = ('tvmanager.db','tvmanager.db-wal','tvmanager.db-shm')


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def _write(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,indent=2),encoding='utf-8')
    os.replace(temp,path)


def inspect(path):
    path=Path(path).resolve()
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Select a nonempty TV Manager database backup.')
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2)) as con:
        con.execute('PRAGMA query_only=ON')
        if con.execute('PRAGMA quick_check').fetchone()[0]!='ok':
            raise ValueError('The backup failed its SQLite integrity check.')
        for table, columns in CORE.items():
            if not columns.issubset({r[1] for r in con.execute('PRAGMA table_info('+table+')')}):
                raise ValueError('This is not a compatible TV Manager backup: '+table)
        counts={table:con.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in CORE}
        # Orphaned episodes must never silently enter a restored library.
        if con.execute('SELECT 1 FROM episodes e LEFT JOIN shows s ON s.id=e.show_id WHERE s.id IS NULL LIMIT 1').fetchone():
            raise ValueError('The backup contains episodes without a show.')
    return dict(path=str(path),size=path.stat().st_size,sha256=digest(path),counts=counts)


def preview(base, source, config_directory=None):
    base=Path(base).resolve();source=Path(source)
    if source.is_symlink():raise ValueError('Select the original backup file.')
    source=source.resolve()
    if source.suffix.lower()=='.zip':
        with zipfile.ZipFile(source) as archive:
            entries=[i for i in archive.infolist() if i.filename=='tvmanager.db']
            if len(entries)!=1 or stat.S_ISLNK(entries[0].external_attr>>16):
                raise ValueError('The ZIP must contain exactly one regular tvmanager.db file.')
            entry=entries[0]
            if entry.file_size>100*1024**3 or entry.file_size>shutil.disk_usage(base).free//2:
                raise ValueError('The backup is too large to restore with the available space.')
            folder=base/'recovery'/'uploads'/uuid.uuid4().hex;folder.mkdir(parents=True)
            target=folder/'tvmanager.db'
            with archive.open(entry) as src,target.open('xb') as dst:
                written=0
                while chunk:=src.read(1024*1024):
                    written+=len(chunk)
                    if written>entry.file_size:raise ValueError('Invalid ZIP backup size.')
                    dst.write(chunk)
            source=target
    if source==base/'tvmanager.db':
        raise ValueError('Select a backup, not the active library database.')
    if source.is_symlink():
        raise ValueError('Select the original backup file.')
    report=inspect(source)
    report['config']=[]
    if config_directory:
        folder=Path(config_directory).resolve()
        if not folder.is_relative_to(base/'backups'/'config'):
            raise ValueError('Select a configuration snapshot from Database Safety.')
        manifest=json.loads((folder/'config-backup.json').read_text(encoding='utf-8'))
        for row in manifest.get('files',[]):
            file=Path(row['backup']).resolve()
            if file.name not in CONFIG or row.get('redacted'):
                continue
            if file.parent!=folder or not file.is_file() or digest(file)!=row.get('sha256'):
                raise ValueError('Configuration snapshot is missing or has changed.')
            report['config'].append(dict(path=str(file),name=file.name,sha256=digest(file)))
        if not report['config']:
            raise ValueError('This snapshot contains no restorable configuration. Redacted files cannot restore secrets.')
    return report


def status(base):
    path=Path(base)/'recovery'/'restore.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'status':'none'}


@serialized
def stage(base, reviewed):
    base=Path(base).resolve();root=base/'recovery';root.mkdir(exist_ok=True)
    if status(base)['status'] in {'pending','applying','validating'}:
        raise ValueError('A restore is already queued. Cancel it before selecting another backup.')
    source=Path(reviewed['path'])
    if inspect(source)['sha256']!=reviewed['sha256']:
        raise ValueError('The backup changed. Preview it again.')
    required=source.stat().st_size+(base/'tvmanager.db').stat().st_size if (base/'tvmanager.db').exists() else source.stat().st_size
    if shutil.disk_usage(base).free<required*2:
        raise ValueError('Not enough free disk space to stage the restore and preserve rollback files.')
    ident=uuid.uuid4().hex;folder=root/ident;folder.mkdir()
    incoming=folder/'incoming';incoming.mkdir()
    shutil.copy2(source,incoming/'tvmanager.db')
    if inspect(incoming/'tvmanager.db')['sha256']!=reviewed['sha256']:
        raise ValueError('Backup changed while it was copied. Preview it again.')
    hashes={'tvmanager.db':reviewed['sha256']}
    for row in reviewed.get('config',[]):
        if row['name'] not in CONFIG:
            raise ValueError('Unsupported configuration file.')
        shutil.copy2(row['path'],incoming/row['name'])
        if digest(incoming/row['name'])!=row['sha256']:
            raise ValueError('Configuration changed. Preview it again.')
        hashes[row['name']]=row['sha256']
    journal=dict(status='pending',id=ident,source=str(source),counts=reviewed['counts'],
                 hashes=hashes,created_at=datetime.now(timezone.utc).isoformat(),message='Restore queued for the next normal restart. Current library changes made before restart will be preserved in the rollback copy.')
    _write(root/'restore.json',journal)
    return journal


@serialized
def cancel(base):
    journal=status(base)
    if journal['status']!='pending':
        raise ValueError('There is no pending restore to cancel.')
    journal.update(status='cancelled',message='Restore cancelled. The current library was not changed.')
    _write(Path(base)/'recovery'/'restore.json',journal)
    return journal


def _folder(base,journal):
    ident=journal.get('id','')
    if len(ident)!=32 or any(c not in '0123456789abcdef' for c in ident):
        raise ValueError('Invalid restore journal.')
    return Path(base)/'recovery'/ident


def _rollback(base,journal):
    folder=_folder(base,journal)
    for name,existed in journal['originals'].items():
        if name not in (*DATABASE_FILES,*CONFIG):raise ValueError('Invalid rollback file.')
        target=base/name
        if existed:
            temp=folder/('rollback-'+name)
            shutil.copy2(folder/'before'/name,temp)
            os.replace(temp,target)
        elif target.exists():
            # Preserve the failed replacement as evidence instead of deleting it.
            os.replace(target,folder/('failed-'+name))
    journal.update(status='rolled_back',message='The restore did not finish startup. The previous library and configuration were restored.')
    _write(base/'recovery'/'restore.json',journal)


def apply_pending(base):
    """Call only while holding the installation lease, before opening application DBs."""
    base=Path(base).resolve();journal=status(base)
    if journal['status'] in {'applying','validating'}:
        _rollback(base,journal)
        return status(base)
    if journal['status']!='pending':return journal
    folder=_folder(base,journal);incoming=folder/'incoming'
    try:
        for name,checksum in journal['hashes'].items():
            if name not in ('tvmanager.db',*CONFIG) or digest(incoming/name)!=checksum:
                raise ValueError('Staged restore files changed. Restore refused.')
        inspect(incoming/'tvmanager.db')
        before=folder/'before';before.mkdir(exist_ok=True)
        originals={}
        for name in (*DATABASE_FILES,*[n for n in journal['hashes'] if n!='tvmanager.db']):
            originals[name]=(base/name).exists()
            if originals[name]:shutil.copy2(base/name,before/name)
        journal.update(status='applying',originals=originals)
        _write(base/'recovery'/'restore.json',journal)
        for name in DATABASE_FILES[1:]:
            if (base/name).exists():os.replace(base/name,folder/('displaced-'+name))
        for name in journal['hashes']:
            temp=folder/('apply-'+name);shutil.copy2(incoming/name,temp);os.replace(temp,base/name)
        inspect(base/'tvmanager.db')
        # Remote client queues cannot be rolled back with a local database.
        with closing(sqlite3.connect(base/'tvmanager.db')) as c:
            c.execute("UPDATE settings SET value='0' WHERE lower(section)='tvmanager' AND lower(name)='automation_enabled'")
            c.execute("UPDATE settings SET value='1' WHERE lower(section)='tvmanager' AND lower(name)='simulation_mode'")
            c.commit()
        journal.update(status='validating',message='Restored files installed; checking application startup.')
        _write(base/'recovery'/'restore.json',journal)
    except Exception as exc:
        if journal['status']=='applying':_rollback(base,journal)
        journal=status(base)
        journal.update(status='failed' if journal['status']!='rolled_back' else 'rolled_back',message=str(exc))
        _write(base/'recovery'/'restore.json',journal)
        raise RuntimeError('Restore failed; the previous library was retained. '+str(exc)) from exc
    return journal


def startup_complete(base):
    journal=status(base)
    if journal['status']=='validating':
        journal.update(status='complete',message='Restore complete. The previous library is retained in the rollback folder. Automation is paused; review downloader queues before enabling it.',completed_at=datetime.now(timezone.utc).isoformat())
        _write(Path(base)/'recovery'/'restore.json',journal)
    return journal
