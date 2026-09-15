"""Run real Flask initialization and routes only in a clean temporary installation."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import pytest
import media_transfer


@pytest.mark.parametrize('selected',['move','copy','hardlink','symlink','symlink_reversed'])
def test_media_methods_preserve_identity_and_undo(tmp_path,selected):
    source=tmp_path/'source.mkv';dest=tmp_path/'episode.mkv';source.write_bytes(b'synthetic media')
    if 'symlink' in selected:
        try:media_transfer.check_links(tmp_path,selected)
        except ValueError:pytest.skip('This Windows account lacks symbolic-link permission')
    operation=media_transfer.transfer(source,dest,selected)
    assert dest.read_bytes()==b'synthetic media'
    if selected=='symlink':assert source.is_symlink() and not dest.is_symlink()
    if selected=='symlink_reversed':assert dest.is_symlink() and not source.is_symlink()
    media_transfer.undo(operation)
    assert source.read_bytes()==b'synthetic media' and not dest.exists()


def test_clean_install_routes_and_subscription_scope(tmp_path):
    root=Path(__file__).resolve().parents[1]
    for source in root.glob('*.py'):shutil.copy2(source,tmp_path/source.name)
    for name in ['VERSION','settings_defaults.json','RELEASE_MANIFEST.json']:shutil.copy2(root/name,tmp_path/name)
    for name in ['templates','static']:shutil.copytree(root/name,tmp_path/name)
    check=tmp_path/'check_routes.py'
    check.write_text("""
import json
from datetime import date
import app
import engine
import database_safety
app.security.browser_auth_enabled=lambda:True
app.security.admin_configured=lambda:True
client=app.app.test_client()
with client.session_transaction() as session:
    session['admin_user']='fixture-admin';app.security.csrf_value(session)
assert app.BASE==__import__('pathlib').Path(__file__).resolve().parent
assert client.get('/database-safety').status_code==200
with client.session_transaction() as session:csrf=session['csrf_token']
headers={'X-CSRF-Token':csrf}
assert client.post('/api/protection/restore/cancel').status_code==403
assert client.get('/api/calendar?start=2026-09-01&end=2026-09-30').status_code==200
assert client.get('/api/calendar?start=invalid').status_code==400
assert client.get('/calendar.ics').data.startswith(b'BEGIN:VCALENDAR')
assert client.get('/api/postprocess/scripts').status_code==200
assert client.post('/api/postprocess/config',json={'process_method':'delete'},headers=headers).status_code==400
assert client.patch('/api/settings/section/TVManager/background_worker_limit',json={'value':'99'},headers=headers).status_code==400
assert client.get('/api/downloaders/handoffs').get_json()['results']==[]
assert client.get('/api/providers/manage').status_code==200
provider=client.post('/api/providers/custom',json={'name':'Route Fixture','url':'https://fixture.test/api','enabled':False,'enable_daily':False},headers=headers)
assert provider.status_code==200,provider.data
pid=provider.get_json()['id']
assert client.get('/api/providers/manage').get_json()['results'][0]['enabled']==0
assert client.patch('/api/providers/manage/custom-'+str(pid),json={'enabled':False,'enable_daily':True}).status_code==403
assert client.patch('/api/providers/manage/custom-'+str(pid),json={'enabled':False,'enable_daily':True},headers=headers).status_code==200
assert client.get('/api/providers/manage').get_json()['results'][0]['enable_daily']==1
assert client.get('/shows/1/metadata-change').status_code==200
assert client.post('/api/shows/1/metadata-change/apply',json={'token':'invalid','confirmation':'CHANGE'},headers=headers).status_code==400
backup=database_safety.backup_database(app.DB,reason='route-test')['backup']
r=client.post('/api/protection/restore/preview',json={'path':backup},headers=headers);assert r.status_code==200,r.data
preview=r.get_json();assert 'token' in preview
assert client.post('/api/protection/restore/stage',json={'token':preview['token']+'changed','confirmation':'RESTORE'},headers=headers).status_code==400
r=client.post('/api/protection/restore/stage',json={'token':preview['token'],'confirmation':'RESTORE'},headers=headers);assert r.status_code==200,r.data
assert client.post('/api/protection/restore/cancel',headers=headers).status_code==200
url=client.post('/api/calendar/subscription',headers=headers).get_json()['url']
token=url.split('token=')[1]
app.security.browser_auth_enabled=lambda:True
app.security.admin_configured=lambda:True
guest=app.app.test_client()
assert guest.get('/calendar.ics?token='+token).status_code==200
assert guest.get('/api/settings/sections?token='+token).status_code==401
assert guest.post('/calendar.ics?token='+token).status_code in (302,401,403,405)
engine.set_setting('TVManager','calendar_token_hash','')
assert guest.get('/calendar.ics?token='+token).status_code in (302,401)
print('Clean install, typed settings, restore review, calendar scope and revocation passed')
""",encoding='utf-8')
    env=os.environ.copy();env.pop('TVMANAGER_BUILDING_EXE',None)
    result=subprocess.run([sys.executable,str(check)],cwd=tmp_path,env=env,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
