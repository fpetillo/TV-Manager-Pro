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
for route in ['/library-health','/library-health/','/library_health','/health/library']:
    page=client.get(route)
    assert page.status_code==200 and b'/static/workflow_recovery.js' in page.data and b'/static/library_health.js' in page.data

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
with app.cx() as c:
    c.execute("INSERT INTO shows(id,name,status) VALUES(1,'Resolution One','Active'),(2,'Resolution Two','Ended')")
assert client.get('/api/shows/resolution/options').get_json()['total']==2
body={'scope':'all','resolution':'1080p','make_default':True}
assert client.post('/api/shows/resolution/preview',json=body).status_code==403
r=client.post('/api/shows/resolution/preview',json=body,headers=headers)
assert r.status_code==200,r.data
review=r.get_json();assert review['plan']['count']==2
assert client.post('/api/shows/resolution/apply',json={'token':review['token']+'bad'},headers=headers).status_code==400
assert client.post('/api/shows/resolution/apply',json=['invalid'],headers=headers).status_code==400
assert client.post('/api/shows/resolution/apply',json={'token':review['token']}).status_code==403
r=client.post('/api/shows/resolution/apply',json={'token':review['token']},headers=headers)
assert r.status_code==200 and r.get_json()['changed']==2,r.data
assert client.get('/api/shows/1?fast=1').get_json()['show']['preferred_resolution']=='1080p'
assert client.get('/api/shows/defaults').get_json()['preferences']['preferred_resolution']=='1080p'
assert client.get('/api/show-queue').get_json()['results'][0]['quality']=='1080p'
assert client.patch('/api/shows/1/options',json={'preferred_resolution':'720p'},headers=headers).status_code==200
assert client.patch('/api/shows/1/options',json={'preferred_resolution':'bad'},headers=headers).status_code==400
assert client.post('/api/shows/resolution/apply',json={'token':review['token']},headers=headers).status_code==400
assert client.post('/api/shows/1/metadata-change/apply',json={'token':'invalid','confirmation':'CHANGE'},headers=headers).status_code==400
# Folder correction is offered before metadata is sent to a worker/provider.
from pathlib import Path
import time
root=Path('fixture-tv');root.mkdir();root=root.resolve()
engine.set_setting('General','root_dirs','0|'+str(root))
metadata_calls=[]
app.metadata_service.refresh_show=lambda sid:metadata_calls.append(sid) or {'show_id':sid,'inserted':0,'updated':0}
for endpoint in ['/api/shows/1/refresh','/api/shows/1/refresh/start']:
    response=client.post(endpoint,headers=headers)
    assert response.status_code==409 and response.get_json()['code']=='show_folder_required',response.data
assert metadata_calls==[]
destination={'library_root':str(root),'folder_name':'Resolution One','previous_location':'','create_directory':True}
assert client.patch('/api/shows/1/destination',json=destination).status_code==403
response=client.patch('/api/shows/1/destination',json=destination,headers=headers)
assert response.status_code==200,response.data
assert (root/'Resolution One').is_dir()
assert client.post('/api/shows/1/refresh',headers=headers).status_code==200
assert metadata_calls==[1]
with app.cx() as c:c.execute('UPDATE shows SET location=? WHERE id=1',(str(root/'Missing'),))
assert client.post('/api/shows/1/refresh/start',headers=headers).status_code==409
destination.update(previous_location=str(root/'Missing'),folder_name='Repaired')
assert client.patch('/api/shows/1/destination',json=destination,headers=headers).status_code==200
def wait_job(start):
    assert start.status_code==200,start.data
    jid=start.get_json()['job']['job_id']
    for attempt in range(100):
        job=client.get('/api/jobs/'+jid).get_json()['job']
        if job['status'] in ['complete','error','cancelled']:return job
        time.sleep(.02)
    raise AssertionError('Job did not finish')
assert wait_job(client.post('/api/shows/1/refresh/start',headers=headers))['status']=='complete'
# Force requires a signed review and keeps the existing download.
with app.cx() as c:
    c.execute("INSERT INTO episodes(id,show_id,season,episode,status) VALUES(1,2,1,1,'Wanted')")
    c.execute("INSERT INTO search_results(id,episode_id,provider,protocol,title,url,guid) VALUES(1,1,'Fixture','nzb','Resolution.Two.S01E01.1080p.WEB','https://fixture.test/file','fixture')")
    c.execute("INSERT INTO downloads(id,episode_id,search_result_id,client,status,external_id) VALUES(1,1,1,'Fixture','Queued','original')")
sent=[]
engine.handoff_adapter=lambda result:('Fixture',lambda:sent.append(result['id']) or 'new-id')
engine.advanced.fire_webhooks=lambda *a,**k:None
response=client.post('/api/search-results/1/grab',json={'force':True},headers=headers)
assert response.status_code==409 and response.get_json()['force_available'] and sent==[]
job=wait_job(client.post('/api/search-results/1/grab/start',headers=headers))
assert job['status']=='error' and job['result']['recovery']['force_available']
assert client.post('/api/search-results/1/force-preview').status_code==403
response=client.post('/api/search-results/1/force-preview',headers=headers)
assert response.status_code==200,response.data
force_token=response.get_json()['token']
assert client.post('/api/search-results/1/grab/start',json={'force_token':force_token+'bad'},headers=headers).status_code==400
assert client.post('/api/search-results/1/grab',json={'force_token':force_token}).status_code==403
assert client.post('/api/search-results/2/grab',json={'force_token':force_token},headers=headers).status_code==400
job=wait_job(client.post('/api/search-results/1/grab/start',json={'force_token':force_token},headers=headers))
assert job['status']=='complete' and sent==[1],job
assert client.post('/api/search-results/1/grab',json={'force_token':force_token},headers=headers).status_code==400
with app.cx() as c:
    assert c.execute('SELECT COUNT(*) FROM downloads').fetchone()[0]==2
    assert c.execute('SELECT external_id FROM downloads WHERE id=1').fetchone()[0]=='original'
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
