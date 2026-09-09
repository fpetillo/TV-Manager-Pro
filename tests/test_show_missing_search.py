import sqlite3
from contextlib import contextmanager
import pytest
import show_missing_search as search

@pytest.fixture
def db(tmp_path,monkeypatch):
    path=tmp_path/'test.db'
    @contextmanager
    def cx():
        c=sqlite3.connect(path);c.row_factory=sqlite3.Row
        try: yield c;c.commit()
        finally: c.close()
    monkeypatch.setattr(search.engine,'cx',cx)
    monkeypatch.setattr(search.engine,'ignore_specials_from_wanted',lambda:True)
    with cx() as c:
        c.executescript("""CREATE TABLE shows(id,name,paused,search_enabled);
        INSERT INTO shows VALUES(1,'Test',0,1),(2,'Other',0,1);
        CREATE TABLE episodes(id,show_id,season,episode,status,location,monitored,ignored,airdate);
        CREATE TABLE downloads(episode_id,status);""")
        for eid in range(1,36):
            c.execute("INSERT INTO episodes VALUES(?,1,1,?,'Wanted','',1,0,'2020-01-01')",(eid,eid))
    return cx

def test_all_seasons_uncapped_and_exclusions(db):
    assert len(search.candidates(1))==35
    with db() as c:
        for eid,assignment in enumerate(["location='file.mkv'","ignored=1","monitored=0","airdate='2999-01-01'","status='Snatched'","season=0","airdate=NULL","show_id=2","status='Downloaded'"],1):
            c.execute(f'UPDATE episodes SET {assignment} WHERE id=?',(eid,))
        c.execute("INSERT INTO downloads VALUES(10,'Queued')")
        c.execute("INSERT INTO downloads VALUES(11,'Failed')")
    assert search.candidates(1)==list(range(11,36))
    assert search.candidates(1,12)==[12]
    with db() as c:c.execute('UPDATE shows SET paused=1 WHERE id=1')
    with pytest.raises(ValueError):search.candidates(1)

def test_worker_continues_after_error_and_simulation(db,monkeypatch):
    calls=[]
    monkeypatch.setattr(search.engine,'get_setting',lambda *a:'1')
    def episode(eid,auto_grab):
        calls.append((eid,auto_grab))
        if eid==1:raise ValueError('Provider failed')
        return {'results':[], 'grabbed':None}
    monkeypatch.setattr(search.engine,'search_episode',episode)
    def synchronous(kind,worker,**kwargs):
        job=search.job_center.create_job(kind,**kwargs);worker(job['job_id']);return search.job_center.get_job(job['job_id'])
    monkeypatch.setattr(search.job_center,'run_background',synchronous)
    job=search.start(1)
    assert len(calls)==35 and all(not auto for _,auto in calls)
    assert job['failed']==1 and job['result']['not_found']==34 and job['processed']==35

def test_repeated_start_returns_active_job(db,monkeypatch):
    job=search.job_center.create_job('show_missing_search')
    monkeypatch.setitem(search._active,1,job['job_id'])
    assert search.start(1)['job_id']==job['job_id']
    search.job_center.update_job(job['job_id'],status='complete')


def test_handoff_and_recheck_skip_newly_queued_episode(db,monkeypatch):
    calls=[]
    monkeypatch.setattr(search.engine,'get_setting',lambda *a:'0')
    def episode(eid,auto_grab):
        assert auto_grab
        calls.append(eid)
        if eid==1:
            with db() as c:c.execute("UPDATE episodes SET status='Snatched' WHERE id=2")
        return {'grabbed':{'ok':True}}
    monkeypatch.setattr(search.engine,'search_episode',episode)
    def synchronous(kind,worker,**kwargs):
        job=search.job_center.create_job(kind,**kwargs);worker(job['job_id']);return search.job_center.get_job(job['job_id'])
    monkeypatch.setattr(search.job_center,'run_background',synchronous)
    result=search.start(1)['result']
    assert result['queued']==34 and result['skipped']==1 and 2 not in calls
