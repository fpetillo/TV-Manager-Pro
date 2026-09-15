import json
import sqlite3
from contextlib import closing
import pytest
import library_recovery as recovery
import job_center


def make_database(path,name):
    with closing(sqlite3.connect(path)) as c:
        c.executescript('CREATE TABLE shows(id,name); CREATE TABLE episodes(id,show_id,season,episode); CREATE TABLE settings(section,name,value);')
        c.execute('INSERT INTO shows VALUES(1,?)',(name,))
        c.execute('INSERT INTO episodes VALUES(1,1,1,1)');c.commit()


def title(path):
    with closing(sqlite3.connect(path)) as c:return c.execute('SELECT name FROM shows').fetchone()[0]


def test_restore_stages_then_applies_and_retains_rollback(tmp_path):
    live=tmp_path/'tvmanager.db';backup=tmp_path/'backup.db'
    make_database(live,'Current');make_database(backup,'Backup')
    plan=recovery.preview(tmp_path,backup)
    assert plan['counts']['episodes']==1
    job=recovery.stage(tmp_path,plan)
    assert title(live)=='Current' and job['status']=='pending'
    recovery.apply_pending(tmp_path)
    assert title(live)=='Backup'
    recovery.startup_complete(tmp_path)
    assert recovery.status(tmp_path)['status']=='complete'
    assert title(tmp_path/'recovery'/job['id']/'before'/'tvmanager.db')=='Current'


def test_incomplete_startup_rolls_back_database_and_configuration(tmp_path):
    live=tmp_path/'tvmanager.db';backup=tmp_path/'backup.db'
    make_database(live,'Current');make_database(backup,'Backup')
    (tmp_path/'.env').write_text('TEST=original',encoding='utf-8')
    folder=tmp_path/'backups'/'config'/'fixture';folder.mkdir(parents=True)
    config=folder/'.env';config.write_text('TEST=restored',encoding='utf-8')
    (folder/'config-backup.json').write_text(json.dumps({'files':[{'backup':str(config),'sha256':recovery.digest(config),'redacted':False}]}),encoding='utf-8')
    recovery.stage(tmp_path,recovery.preview(tmp_path,backup,folder));recovery.apply_pending(tmp_path)
    assert (tmp_path/'.env').read_text()=='TEST=restored'
    # Simulate startup failing before its final validation checkpoint.
    recovery.apply_pending(tmp_path)
    assert title(live)=='Current' and (tmp_path/'.env').read_text()=='TEST=original'
    assert recovery.status(tmp_path)['status']=='rolled_back'


def test_restore_rejects_changed_backup_and_cancel_preserves_live(tmp_path):
    live=tmp_path/'tvmanager.db';backup=tmp_path/'backup.db'
    make_database(live,'Current');make_database(backup,'Backup')
    plan=recovery.preview(tmp_path,backup)
    with closing(sqlite3.connect(backup)) as c:c.execute("UPDATE shows SET name='Changed'");c.commit()
    with pytest.raises(ValueError,match='changed'):recovery.stage(tmp_path,plan)
    recovery.stage(tmp_path,recovery.preview(tmp_path,backup))
    recovery.cancel(tmp_path);recovery.apply_pending(tmp_path)
    assert title(live)=='Current'
    with pytest.raises(ValueError,match='active'):recovery.preview(tmp_path,live)


def test_persisted_jobs_reconcile_without_replaying_work(tmp_path,monkeypatch):
    monkeypatch.setattr(job_center,'_STORE',None)
    monkeypatch.setattr(job_center,'_JOBS',{})
    store=tmp_path/'jobs.sqlite3'
    job_center.configure(store)
    a=job_center.create_job('postprocess');b=job_center.create_job('metadata')
    job_center.update_job(a['job_id'],status='complete',result={'processed':2})
    job_center.update_job(b['job_id'],status='running',processed=1)
    job_center.configure(store)
    assert job_center.get_job(a['job_id'])['result']=={'processed':2}
    interrupted=job_center.get_job(b['job_id'])
    assert interrupted['status']=='error' and interrupted['interrupted'] and interrupted['processed']==1


def test_queue_limit_rejects_new_work_without_pruning_active_jobs(monkeypatch):
    monkeypatch.setattr(job_center,'_STORE',None);monkeypatch.setattr(job_center,'_JOBS',{})
    monkeypatch.setattr(job_center,'_MAX_PENDING',1)
    job=job_center.create_job('test')
    with pytest.raises(ValueError,match='queue is full'):job_center.create_job('test')
    assert job_center.get_job(job['job_id'])['status']=='queued'
