import threading
import pytest
import acquisition_journal as journal
import dbcore


@pytest.fixture
def db(tmp_path):
    database=tmp_path/'tvmanager.db'
    with dbcore.connect(database) as c:
        c.executescript("""CREATE TABLE episodes(id PRIMARY KEY,show_id,season);
        INSERT INTO episodes VALUES(1,1,1),(2,1,1),(3,1,2);
        CREATE TABLE downloads(id INTEGER PRIMARY KEY,episode_id,status);
        CREATE TABLE season_pack_downloads(id INTEGER PRIMARY KEY,show_id,season,status);
        """)
    return database


def record(c,payload,client,external):
    row=c.execute("INSERT INTO downloads(episode_id,status) VALUES(?,'Queued')",(payload['episode_id'],))
    return {'download_id':row.lastrowid}


def test_receipt_and_library_record_are_committed(db):
    result=journal.submit(db,'episode',{'episode_id':1},'Test',[1],lambda:'remote-id',record)
    assert result['download_id']==1 and journal.listing(db)==[]
    with dbcore.connect(db) as c:
        row=c.execute('SELECT * FROM acquisition_intents').fetchone()
        assert row['external_id']=='remote-id' and row['state']=='recorded'
        assert not c.execute('SELECT * FROM acquisition_reservations').fetchall()
    with pytest.raises(ValueError,match='active download'):journal.reserve(db,'episode',{},'Test',[1])


def test_timeout_preserves_hold_until_review(db):
    calls=[]
    def timeout():calls.append(1);raise TimeoutError('secret URL must not enter public message')
    with pytest.raises(ValueError,match='requires review'):journal.submit(db,'episode',{'episode_id':1},'Test',[1],timeout,record)
    rows=journal.listing(db);assert len(rows)==1 and rows[0]['state']=='uncertain'
    with pytest.raises(ValueError,match='unresolved'):journal.submit(db,'episode',{},'Test',[1],timeout,record)
    assert calls==[1]
    journal.resolve(db,rows[0]['id'],'not_sent')
    assert journal.submit(db,'episode',{'episode_id':1},'Test',[1],lambda:'second',record)


def test_database_failure_retains_remote_receipt(db):
    def failed(*args):raise RuntimeError('DB unavailable after client accepted')
    with pytest.raises(ValueError):journal.submit(db,'episode',{'episode_id':1},'Test',[1],lambda:'accepted-id',failed)
    row=journal.listing(db)[0]
    assert row['state']=='accepted' and row['external_id']=='accepted-id'
    journal.finish(db,row['id'],row['external_id'],record)
    assert journal.listing(db)==[]


def test_season_pack_overlap_and_all_or_nothing_reservations(db):
    with dbcore.connect(db) as c:c.execute("INSERT INTO season_pack_downloads VALUES(1,1,1,'Queued')")
    with pytest.raises(ValueError,match='season pack'):journal.reserve(db,'episode',{},'Test',[2])
    with pytest.raises(ValueError):journal.reserve(db,'season_pack',{},'Test',[3,1])
    assert journal.reserve(db,'episode',{},'Test',[3])


def test_resolution_cannot_race_active_sender(db):
    started=threading.Event();finish=threading.Event();outcome=[]
    def sender():started.set();finish.wait(3);return 'receipt'
    def worker():outcome.append(journal.submit(db,'episode',{'episode_id':1},'Test',[1],sender,record))
    task=threading.Thread(target=worker);task.start();assert started.wait(2)
    token=journal.listing(db)[0]['id']
    try:
        with pytest.raises(ValueError,match='operation'):journal.resolve(db,token,'not_sent')
    finally:finish.set();task.join(3)
    assert outcome and journal.listing(db)==[]
