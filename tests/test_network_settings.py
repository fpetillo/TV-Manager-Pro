import sqlite3
from contextlib import closing
import pytest
import network_settings as network


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'network.db'
    with closing(sqlite3.connect(path)) as c:
        c.execute('CREATE TABLE settings(section TEXT,name TEXT,value TEXT,is_secret INTEGER,source TEXT,updated_at TEXT)')
        c.execute("INSERT INTO settings VALUES('General','keep','unchanged',0,'fixture','')")
        c.commit()
    return path


@pytest.mark.parametrize('host,port', [('http://192.168.1.11',5050), ('127.evil.test',5050), ('239.1.1.1',5050), ('255.255.255.255',5050), ('127.0.0.1',0), ('127.0.0.1',65536), ('127.0.0.1',True), ('127.0.0.1',1.5), ('',5050)])
def test_invalid_values_rejected(host, port):
    with pytest.raises(ValueError): network.validate(host, port)


def test_persistence_precedence_and_pending_restart(database, monkeypatch):
    calls=[]
    monkeypatch.setattr(network,'ensure_local_address',lambda host:calls.append(host))
    active=network.read(database, {'HOST':'127.0.0.1','PORT':'5050'})
    network.save(database, {'host':'192.168.1.11','port':5050}, True, True, {})
    result=network.status(database, active, {'HOST':'127.0.0.1','PORT':'5050'})
    assert result['config']=={'host':'192.168.1.11','port':5050} and result['restart_required']
    assert result['active']==active and result['url']=='http://192.168.1.11:5050'
    assert not network.status(database, result['config'], {})['restart_required']
    assert calls==['192.168.1.11']
    assert network.read(database, {'TVMANAGER_BIND_HOST':'127.0.0.1','TVMANAGER_BIND_PORT':'5054'})=={'host':'127.0.0.1','port':5054}
    with pytest.raises(ValueError,match='override'):network.save(database, active, True, True, {'TVMANAGER_BIND_HOST':'127.0.0.1'})
    with closing(sqlite3.connect(database)) as c:
        assert c.execute("SELECT value FROM settings WHERE name='keep'").fetchone()[0]=='unchanged'


@pytest.mark.parametrize('admin,auth',[(False,False),(True,False),(False,True)])
def test_lan_requires_login_before_save_and_start(database,admin,auth):
    config={'host':'0.0.0.0','port':5050}
    with pytest.raises(ValueError,match='Security'):network.save(database, config, admin, auth, {})
    with pytest.raises(ValueError,match='Security'):network.prepare(config, admin, auth)
    assert network.read(database,{})['host']=='127.0.0.1'


def test_local_only_save_and_ipv6_urls(database):
    config=network.save(database, {'host':'localhost','port':'5054'},False,False,{})
    assert network.prepare(config,False,False)=={'host':'127.0.0.1','port':5054}
    assert network.url(network.validate('::1',5050))=='http://[::1]:5050'
    assert network.url(network.validate('0.0.0.0',5050)) is None


def test_unavailable_interface_preserves_saved_values(database,monkeypatch):
    def unavailable(host):raise ValueError('not available')
    monkeypatch.setattr(network,'ensure_local_address',unavailable)
    with pytest.raises(ValueError,match='not available'):network.save(database,{'host':'192.168.1.11','port':5050},True,True,{})
    assert network.read(database,{})=={'host':'127.0.0.1','port':5050}


def test_offline_recovery_requires_stopped_app_and_preserves_security(tmp_path):
    import shutil, subprocess, sys
    from pathlib import Path
    import runtime_guard
    root=Path(__file__).resolve().parents[1]
    for name in ['configure_network.py','network_settings.py','app_paths.py','runtime_guard.py','media_operations.py','dbcore.py','security.py']:
        shutil.copy2(root/name,tmp_path/name)
    db=tmp_path/'tvmanager.db'
    with closing(sqlite3.connect(db)) as c:
        c.executescript("CREATE TABLE settings(section TEXT,name TEXT,value TEXT,is_secret INTEGER,source TEXT,updated_at TEXT); CREATE TABLE admin_users(enabled INTEGER); INSERT INTO admin_users VALUES(1); INSERT INTO settings VALUES('TVManager','browser_auth_enabled','1',0,'fixture','');")
    command=[sys.executable,str(tmp_path/'configure_network.py'),'--host','127.0.0.1','--port','5056']
    runtime_guard.acquire(tmp_path)
    try:
        blocked=subprocess.run(command,cwd=tmp_path,capture_output=True,text=True,timeout=10)
        assert blocked.returncode!=0 and 'already running' in blocked.stderr
    finally:runtime_guard.release()
    result=subprocess.run(command,cwd=tmp_path,capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert network.read(db,{})=={'host':'127.0.0.1','port':5056}
    with closing(sqlite3.connect(db)) as c:
        assert c.execute("SELECT value FROM settings WHERE name='browser_auth_enabled'").fetchone()[0]=='1'
