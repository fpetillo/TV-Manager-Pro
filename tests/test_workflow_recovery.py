from pathlib import Path
import pytest
import dbcore
import engine
import acquisition_journal as journal
import download_override as override
import show_folder


@pytest.fixture
def downloads(tmp_path,monkeypatch):
    database=tmp_path/'library.db'
    monkeypatch.setattr(engine,'DB',database)
    with dbcore.connect(database) as c:
        c.executescript('''
        CREATE TABLE shows(id INTEGER PRIMARY KEY,name,preferred_resolution,quality_profile_id);
        CREATE TABLE episodes(id INTEGER PRIMARY KEY,show_id,season,episode,status,release_name);
        CREATE TABLE search_results(id INTEGER PRIMARY KEY,episode_id,provider,protocol,title,url,guid,rejected_reason,status);
        CREATE TABLE downloads(id INTEGER PRIMARY KEY,episode_id,search_result_id,client,provider,release_name,external_id,status,url);
        CREATE TABLE season_pack_downloads(id INTEGER PRIMARY KEY,show_id,season,status,client,title);
        CREATE TABLE failed_releases(guid);
        CREATE TABLE settings(section,name,value);
        INSERT INTO shows VALUES(1,'Review Show','1080p',NULL);
        INSERT INTO episodes VALUES(1,1,1,1,'Downloaded','Original release');
        INSERT INTO search_results VALUES(1,1,'Fixture','nzb','Review.Show.S01E01.1080p.WEB','https://fixture.test/release','fixture-guid',NULL,'Found');
        INSERT INTO downloads VALUES(1,1,1,'Fixture','Fixture','Original release','old-remote','Queued','');
        ''')
    sent=[]
    monkeypatch.setattr(engine,'handoff_adapter',lambda r:('Fixture',lambda:sent.append(r['id']) or 'new-remote'))
    monkeypatch.setattr(engine,'log',lambda *a,**k:None)
    monkeypatch.setattr(engine.advanced,'fire_webhooks',lambda *a,**k:None)
    monkeypatch.setattr(engine.lifecycle,'transition',lambda *a,**k:None)
    return database,sent


def review(database):
    with dbcore.connect(database) as c:return override.preview(c,1)


@pytest.mark.parametrize('status',['Queued','Downloading','Downloaded','Importing','Completed'])
def test_force_keeps_history_and_submits_once(downloads,status):
    database,sent=downloads
    with dbcore.connect(database) as c:c.execute('UPDATE downloads SET status=?',(status,))
    with pytest.raises(override.DuplicateDownload):engine.grab_result(1)
    plan=review(database)
    result=engine.grab_result(1,force_review=plan)
    assert result['download_id']==2 and sent==[1]
    with dbcore.connect(database) as c:
        assert tuple(c.execute('SELECT status,external_id FROM downloads WHERE id=1').fetchone())==(status,'old-remote')
        intent=c.execute('SELECT payload,state FROM acquisition_intents').fetchone()
        assert '"forced": true' in intent['payload'] and 'old-remote' not in intent['payload']
        assert intent['state']=='recorded'
    with pytest.raises(ValueError,match='changed after review'):engine.grab_result(1,force_review=plan)
    assert sent==[1]


def test_force_reviews_active_season_pack(downloads):
    database,sent=downloads
    with dbcore.connect(database) as c:
        c.execute('DELETE FROM downloads')
        c.execute("INSERT INTO season_pack_downloads VALUES(1,1,1,'Queued','Fixture','Season pack')")
    with pytest.raises(override.DuplicateDownload,match='season pack'):engine.grab_result(1)
    plan=review(database)
    assert plan['conflicts'][0]['kind']=='season pack'
    assert engine.grab_result(1,force_review=plan)['ok'] and sent==[1]
    with dbcore.connect(database) as c:assert c.execute('SELECT status FROM season_pack_downloads').fetchone()[0]=='Queued'


def test_state_changes_invalidate_review_before_network_io(downloads):
    database,sent=downloads
    plan=review(database)
    with dbcore.connect(database) as c:c.execute("UPDATE downloads SET status='Failed'")
    with pytest.raises(ValueError,match='changed after review'):engine.grab_result(1,force_review=plan)
    # The journal repeats validation under its write transaction.
    with pytest.raises(ValueError,match='changed after review'):
        journal.reserve(database,'episode',{'id':1},'Fixture',[1],force_review=plan)
    assert sent==[]


@pytest.mark.parametrize('restriction',['resolution','rejected','blacklist','unresolved'])
def test_force_does_not_override_other_restrictions(downloads,restriction):
    database,sent=downloads
    journal.init(database)
    with dbcore.connect(database) as c:
        if restriction=='resolution':c.execute("UPDATE shows SET preferred_resolution='2160p'")
        elif restriction=='rejected':c.execute("UPDATE search_results SET rejected_reason='Required word missing'")
        elif restriction=='blacklist':c.execute("INSERT INTO failed_releases VALUES('fixture-guid')")
    plan=review(database)
    if restriction=='unresolved':
        with dbcore.connect(database) as c:
            c.execute("INSERT INTO acquisition_intents(id,kind,payload,client,state) VALUES('hold','episode','{}','Fixture','uncertain')")
            c.execute("INSERT INTO acquisition_reservations VALUES(1,'hold')")
    with pytest.raises(ValueError):engine.grab_result(1,force_review=plan)
    assert sent==[]


def test_force_timeout_keeps_reservation_and_blocks_replay(downloads,monkeypatch):
    database,_=downloads
    def timeout():raise TimeoutError('fixture')
    monkeypatch.setattr(engine,'handoff_adapter',lambda r:('Fixture',timeout))
    plan=review(database)
    with pytest.raises(ValueError,match='requires review'):engine.grab_result(1,force_review=plan)
    with pytest.raises(ValueError,match='unresolved'):engine.grab_result(1,force_review=plan)
    assert journal.listing(database)[0]['state']=='uncertain'


def test_missing_folder_can_be_created_without_changing_files(tmp_path):
    root=tmp_path/'TV';root.mkdir()
    existing=root/'keep.mkv';existing.write_bytes(b'keep')
    show={'id':1,'name':'Fixture','location':''}
    assert show_folder.inspect(show,str)['code']=='show_folder_required'
    show['location']=str(root/'Fixture')
    assert show_folder.inspect(show,str)['location']==show['location']
    show_folder.create(str(root),show['location'],str)
    assert show_folder.inspect(show,str) is None and existing.read_bytes()==b'keep'
    show_folder.create(str(root),show['location'],str)  # Existing folder is valid.


def test_missing_root_is_not_silently_created(tmp_path):
    root=tmp_path/'offline';target=root/'Fixture'
    with pytest.raises(ValueError,match='root is unavailable'):show_folder.create(str(root),str(target),str)
    assert not root.exists()


def test_file_is_not_a_valid_destination_and_mapped_paths_work(tmp_path):
    root=tmp_path/'TV';root.mkdir();(root/'File').write_text('keep')
    mapper=lambda value:str(root/value.rsplit('/',1)[-1]) if value!='/remote' else str(root)
    with pytest.raises(ValueError):show_folder.create('/remote','/remote/File',mapper)
    show_folder.create('/remote','/remote/Show',mapper)
    assert show_folder.inspect({'id':1,'name':'Show','location':'/remote/Show'},mapper) is None


def test_download_progress_does_not_invalidate_confirmation(downloads):
    database,sent=downloads
    with dbcore.connect(database) as c:
        c.execute('ALTER TABLE downloads ADD COLUMN progress REAL DEFAULT 0')
        c.execute('ALTER TABLE downloads ADD COLUMN updated_at TEXT')
    plan=review(database)
    with dbcore.connect(database) as c:c.execute("UPDATE downloads SET progress=0.5,updated_at='later'")
    assert engine.grab_result(1,force_review=plan)['ok'] and sent==[1]


@pytest.mark.parametrize('kind',['batch','full','missing'])
def test_bulk_metadata_reports_repair_links_and_respects_mappings(tmp_path,monkeypatch,kind):
    import metadata_service as metadata
    database=tmp_path/'metadata.db'
    monkeypatch.setattr(metadata,'DB',database)
    ready=tmp_path/'ready';ready.mkdir()
    with dbcore.connect(database) as c:
        c.executescript("""
        CREATE TABLE shows(id INTEGER PRIMARY KEY,name,location,paused DEFAULT 0,metadata_enabled DEFAULT 1);
        CREATE TABLE settings(section,name,value);
        CREATE TABLE path_mappings(id INTEGER PRIMARY KEY,name,enabled,remote_path,local_path);
        INSERT INTO shows(id,name,location) VALUES(1,'No folder',''),(2,'Offline','/not/a/real/library'),(3,'Mapped','/remote/ready');
        """)
        c.execute("INSERT INTO path_mappings VALUES(1,'Fixture',1,'/remote/ready',?)",(str(ready),))
    metadata.init()
    refreshed=[]
    monkeypatch.setattr(metadata,'refresh_show',lambda sid:refreshed.append(sid) or {'show_id':sid})
    progress=[]
    if kind=='batch':result=metadata.refresh_batch(limit=10)
    elif kind=='full':
        monkeypatch.setattr(metadata,'_FULL_REFRESH_JOBS',{'fixture':{}})
        metadata._run_full_refresh_job('fixture',[(1,'No folder'),(2,'Offline'),(3,'Mapped')],0)
        result=metadata._job_snapshot('fixture')
        assert result['status']=='complete' and result['succeeded']==3
    else:
        monkeypatch.setattr(metadata,'tmdb_status',lambda:{'configured':True})
        monkeypatch.setattr(metadata,'missing_metadata_candidates',lambda **kwargs:[{'id':i,'name':str(i)} for i in [1,2,3]])
        result=metadata.refresh_missing_metadata(delay_seconds=0,progress_callback=progress.append)
        assert progress[-1]['folder_issues']==result['folder_issues']
    assert sorted(refreshed)==[1,2,3]
    assert {item['show_id'] for item in result['folder_issues']}=={1,2}
    assert all(item['repair_url']==f"/show/{item['show_id']}?repair_folder=1" for item in result['folder_issues'])


def test_episode_search_handles_punctuation_without_executing_titles():
    import shutil,subprocess
    node=shutil.which('node')
    if not node:pytest.skip('Node.js is required for UI event regression')
    root=Path(__file__).resolve().parents[1]
    script=r"""
    const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
    const scope={window:{}};vm.createContext(scope);
    vm.runInContext(fs.readFileSync('static/workflow_recovery.js','utf8'),scope);
    for(const title of ["Wonka's The Golden Ticket",'The "Quoted" Show',"A \\ B",'<img src=x onerror=alert(1)>',"Line\nBreak"]){
      const button={dataset:{searchEpisode:'12'}},seen=[];
      scope.window.searchEpisode=(...args)=>seen.push(args);
      scope.window.bindEpisodeSearch({querySelectorAll:()=>[button]},title,[{id:12,season:1,episode:2}]);
      button.onclick();assert.deepEqual(seen,[[12,title,1,2]]);
    }
    """
    subprocess.run([node,'-e',script],cwd=root,check=True,capture_output=True,text=True)
