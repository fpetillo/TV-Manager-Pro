from contextlib import contextmanager
from pathlib import Path
import sqlite3
import threading
import time
import pytest
import engine
import job_center
import database_safety
import acquisition_guard


@pytest.fixture
def database(tmp_path, monkeypatch):
    path = tmp_path / 'tvmanager.db'
    monkeypatch.setattr(engine, 'DB', path)
    with engine.cx() as c:
        c.executescript('''CREATE TABLE settings(section,name,value,is_secret,source,updated_at,UNIQUE(section,name));
            CREATE TABLE scheduler_jobs(name,enabled);
            CREATE TABLE search_results(id INTEGER PRIMARY KEY,episode_id);
            CREATE TABLE downloads(id INTEGER PRIMARY KEY,episode_id,search_result_id,status);
            INSERT INTO search_results VALUES(1,7),(2,7);
            INSERT INTO scheduler_jobs VALUES('recent_search',1),('post_processing',0);''')
    monkeypatch.setattr(engine, 'log', lambda *a, **k: None)
    return path


def test_automation_preserves_individual_job_choices(database):
    engine.set_automation(False)
    engine.set_automation(True)
    with engine.cx() as c:
        assert [r['enabled'] for r in c.execute('SELECT * FROM scheduler_jobs')] == [1,0]


def test_case_insensitive_settings_update_does_not_create_shadow_value(database):
    engine.set_setting('General', 'process_method', 'copy')
    engine.update_setting_safe('general', 'PROCESS_METHOD', 'move')
    assert engine.get_setting('General','process_method') == 'move'
    with engine.cx() as c:
        assert c.execute('SELECT count(*) FROM settings').fetchone()[0] == 1


def test_duplicate_handoff_does_not_send_again(database, monkeypatch):
    calls=[]
    def send(result_id):
        calls.append(result_id)
        with engine.cx() as c:
            c.execute("INSERT INTO downloads VALUES(1,7,1,'Queued')")
        return {'ok':True}
    monkeypatch.setattr(engine,'_grab_result',send)
    assert engine.grab_result(1)['ok']
    with pytest.raises(ValueError, match='active download'):
        engine.grab_result(2)
    assert calls==[1]


def test_episode_operations_exclude_overlapping_threads(tmp_path):
    errors=[]
    def overlap():
        try:
            with acquisition_guard.exclusive(tmp_path/'db','search',7):
                errors.append('lock incorrectly acquired')
        except ValueError:
            errors.append('blocked')
    with acquisition_guard.exclusive(tmp_path/'db','search',7):
        thread=threading.Thread(target=overlap);thread.start();thread.join(2)
    assert errors==['blocked']
    with acquisition_guard.exclusive(tmp_path/'db','search',7):
        pass


def test_background_limit_and_queued_cancellation(monkeypatch):
    monkeypatch.setattr(job_center,'worker_limit',lambda:1)
    release=threading.Event(); started=threading.Event(); second_started=threading.Event()
    def first(job_id):
        started.set();release.wait(3)
    first_job=job_center.run_background('test',first)
    assert started.wait(2)
    second_job=job_center.run_background('test',lambda job_id:second_started.set(),meta={'cancelable':True})
    try:
        assert job_center.get_job(second_job['job_id'])['status']=='queued'
        job_center.request_cancel(second_job['job_id'])
    finally:
        release.set()
    deadline=time.monotonic()+3
    while time.monotonic()<deadline and job_center.get_job(second_job['job_id'])['status']!='cancelled':
        time.sleep(.01)
    assert job_center.get_job(second_job['job_id'])['status']=='cancelled'
    assert not second_started.is_set()


def test_backup_checks_and_same_second_snapshots(tmp_path, monkeypatch):
    for name, value in {'BACKUPS':tmp_path/'backups','SAFE_BACKUPS':tmp_path/'backups'/'safe','MANIFEST':tmp_path/'backups'/'manifest.json'}.items():
        monkeypatch.setattr(database_safety,name,value)
    absent=tmp_path/'absent.db';empty=tmp_path/'empty.db';empty.touch()
    assert not database_safety.quick_check(absent)['ok']
    assert not database_safety.quick_check(empty)['ok']
    assert not database_safety.backup_database(absent)['ok']
    assert not database_safety.backup_database(empty)['ok']
    database=tmp_path/'source.db'
    with sqlite3.connect(database) as c:c.execute('CREATE TABLE shows(id)')
    monkeypatch.setattr(database_safety,'_stamp',lambda:'same-second')
    a=database_safety.backup_database(database,reason='../../test')
    b=database_safety.backup_database(database,reason='../../test')
    assert a['ok'] and b['ok'] and a['backup']!=b['backup']
    assert Path(a['backup']).parent==database_safety.SAFE_BACKUPS


def route(name, **namespace):
    # Exercise route workers without importing the application or touching its live DB.
    import ast
    from flask import jsonify,request
    source=ast.parse((Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8'))
    node=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name==name)
    node.decorator_list=[]
    namespace.update(jsonify=jsonify,request=request,job_center=job_center)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'app.py','exec'),namespace)
    return namespace[name]


def test_search_and_refresh_workers_report_service_errors(monkeypatch):
    from flask import Flask
    from types import SimpleNamespace
    def synchronous(kind,worker,**kwargs):
        job=job_center.create_job(kind,**kwargs);worker(job['job_id'])
        return job_center.get_job(job['job_id'])
    monkeypatch.setattr(job_center,'run_background',synchronous)
    fake_engine=SimpleNamespace(search_episode=lambda *a,**k:{'results':[],'errors':['Provider unavailable']},
        run_search_job=lambda *a,**k:{'searched':3,'grabbed':0,'errors':['Provider unavailable']})
    fake_media=SimpleNamespace(media_server=lambda *a:{'name':'Test server'},
        refresh_media_server=lambda *a:{'ok':False,'message':'No TV libraries available'})
    application=Flask(__name__)
    with application.test_request_context(json={}):
        for name,args in [('api_episode_search_start',(1,)),('api_run_search_start',('backlog',)),('api_media_server_refresh_start',(1,))]:
            job=route(name,engine=fake_engine,advanced=fake_media)(*args).get_json()['job']
            assert job['status']=='error' and job['errors'] and job['failed']
        fake_engine.run_search_job=lambda *a,**k:{'searched':3,'grabbed':1,'errors':[]}
        job=route('api_run_search_start',engine=fake_engine)('backlog').get_json()['job']
        assert job['status']=='complete' and job['processed']==3


def test_scheduler_records_reported_errors(database,monkeypatch):
    with engine.cx() as c:
        c.execute('CREATE TABLE scheduler_runs(id INTEGER PRIMARY KEY,job_name,status,finished_at,message)')
    statuses=[]
    monkeypatch.setattr(engine.scheduler_guard,'acquire',lambda *a:True)
    monkeypatch.setattr(engine.scheduler_guard,'release',lambda *a:None)
    monkeypatch.setattr(engine,'_finish_job',lambda name,status,message:statuses.append(status))
    monkeypatch.setattr(engine,'run_search_job',lambda *a:{'searched':2,'errors':['Provider unavailable']})
    result=engine.run_job('recent_search')
    assert not result['ok'] and statuses==['Error']
    with engine.cx() as c:
        assert c.execute('SELECT status FROM scheduler_runs').fetchone()[0]=='Error'
