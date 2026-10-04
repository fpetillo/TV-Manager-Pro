from datetime import datetime, timedelta, timezone
import pytest
import dbcore
import library_maintenance
import readiness
import operator_experience


@pytest.fixture
def database(tmp_path):
    db = tmp_path/'readiness.db'
    with dbcore.connect(db) as c:
        c.executescript('''CREATE TABLE settings(section TEXT,name TEXT,value TEXT);
            CREATE TABLE shows(id INTEGER,name TEXT,location TEXT,imdb_id TEXT,tmdb_id INTEGER,tvdb_id INTEGER);
            CREATE TABLE episodes(id INTEGER,show_id INTEGER,season INTEGER,episode INTEGER,name TEXT,status TEXT,location TEXT);
            CREATE TABLE metadata_refresh_state(show_id INTEGER,last_status TEXT,last_refresh TEXT,last_error TEXT);
            CREATE TABLE media_fingerprints(path TEXT,fingerprint TEXT,file_size INTEGER);
            INSERT INTO shows VALUES(1,'Fixture','/library/Fixture','tt123',NULL,NULL);
            INSERT INTO episodes VALUES(1,1,1,1,'Pilot','Wanted','');
            INSERT INTO metadata_refresh_state VALUES(1,'success','2026-10-04','');''')
    readiness.init(db)
    return db


def report(db, network=None):
    health=library_maintenance.library_health_report(db,duplicate_limit=1)
    return readiness.summary(db,'18.11.0',health,{'restart_required':False} if network is None else network)


def verify_all(db):
    for key in readiness.REVIEWS:
        readiness.record(db,'18.11.0',key,{'confirmed':True,'fingerprint':readiness.fingerprint(db,'18.11.0'),
            'evidence':'Synthetic fixture test completed successfully.'},'fixture-operator')


def test_can_reach_100_only_after_every_check_passes(database):
    pending=report(database)
    assert pending['score']<100 and pending['passed']==7
    verify_all(database)
    assert report(database)['score']==100
    assert report(database,{'restart_required':True})['score']<100
    readiness.clear(database,'processing')
    assert report(database)['score']<100


@pytest.mark.parametrize('health',[None,{'ok':False,'counts':{}},{'ok':True,'counts':{}},{'ok':True,'schema_warnings':['check skipped'],'counts':{}}])
def test_unknown_or_failed_health_is_not_clean(database,health):
    verify_all(database)
    result=readiness.summary(database,'18.11.0',health,{'restart_required':False})
    assert result['score']<100 and any(c['status']=='unverified' for c in result['checks'])


def test_real_health_keys_and_full_duplicate_count(database,tmp_path):
    with dbcore.connect(database) as c:
        c.execute("UPDATE shows SET location='',imdb_id=NULL")
        c.execute("UPDATE episodes SET location=?",(str(tmp_path/'absent.mkv'),))
        c.execute("UPDATE metadata_refresh_state SET last_status='error'")
        for group in range(15):
            for copy in range(2):c.execute('INSERT INTO media_fingerprints VALUES(?,?,10)',(f'{group}-{copy}',str(group)))
    health=library_maintenance.library_health_report(database,duplicate_limit=1)
    assert health['counts']['duplicate_groups']==15 and len(health['samples']['duplicates'])==1
    assert health['counts']['missing_episode_files']==1
    data=operator_experience.launchpad_summary(database,'18.11.0',health,{'restart_required':False})
    assert data['counts']['missing_files']==1 and data['counts']['metadata_gaps']==1
    assert all(item['status']=='attention' for item in data['readiness_checklist']['checks'] if item['key'] in {'folders','files','duplicates','ids','metadata'})


def test_mapped_existing_files_and_wanted_empty_paths(database,tmp_path):
    file=tmp_path/'episode.mkv';file.write_bytes(b'fixture')
    with dbcore.connect(database) as c:c.execute("UPDATE episodes SET location='remote/episode.mkv'")
    health=library_maintenance.library_health_report(database,path_mapper=lambda path:str(file))
    assert health['counts']['missing_episode_files']==0
    with dbcore.connect(database) as c:c.execute("UPDATE episodes SET location='' WHERE id=1")
    assert report(database)['checks'][2]['status']=='passed'


def test_configuration_version_expiry_and_stale_reviews(database):
    verify_all(database)
    old=readiness.fingerprint(database,'18.11.0')
    with dbcore.connect(database) as c:c.execute("INSERT INTO settings VALUES('General','naming_pattern','changed')")
    assert report(database)['score']<100
    with pytest.raises(ValueError,match='changed'):
        readiness.record(database,'18.11.0','processing',{'confirmed':True,'fingerprint':old,'evidence':'A previously performed test result.'},'fixture')
    verify_all(database)
    assert readiness.summary(database,'18.12.0',library_maintenance.library_health_report(database),{'restart_required':False})['score']<100
    with dbcore.connect(database) as c:c.execute('UPDATE readiness_evidence SET verified_at=?',((datetime.now(timezone.utc)-timedelta(days=91)).isoformat(),))
    assert report(database)['score']<100


@pytest.mark.parametrize('body',[{},[],{'confirmed':False},{'confirmed':True,'evidence':'ok'}])
def test_review_requires_confirmation_and_evidence(database,body):
    with pytest.raises(ValueError):readiness.record(database,'18.11.0','processing',body,'fixture')


def test_scheduler_progress_does_not_invalidate_saved_verification(database):
    with dbcore.connect(database) as c:
        c.execute('CREATE TABLE scheduler_jobs(name TEXT,enabled INTEGER,interval_minutes INTEGER,next_run TEXT,last_status TEXT)')
        c.execute("INSERT INTO scheduler_jobs VALUES('scan',1,60,'old','ready')")
    verify_all(database)
    with dbcore.connect(database) as c:c.execute("UPDATE scheduler_jobs SET next_run='later',last_status='success'")
    assert report(database)['score']==100
    with dbcore.connect(database) as c:c.execute('UPDATE scheduler_jobs SET interval_minutes=90')
    assert report(database)['score']<100
