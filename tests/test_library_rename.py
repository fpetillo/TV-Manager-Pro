import sqlite3
from pathlib import Path
import pytest
import library_rename as rename
import media_operations
import show_preferences

@pytest.fixture
def library(tmp_path):
    root=tmp_path/'Show';root.mkdir();source=root/'old.mkv';source.write_bytes(b'media')
    db=tmp_path/'test.db'
    c=sqlite3.connect(db)
    c.executescript('CREATE TABLE shows(id INTEGER PRIMARY KEY,name,location,season_folders);CREATE TABLE episodes(id INTEGER PRIMARY KEY,show_id,season,episode,name,location);')
    c.execute('INSERT INTO shows VALUES(1,?,?,1)',('Test Show',str(root)))
    c.execute('INSERT INTO episodes VALUES(1,1,1,1,?,?)',('Pilot',str(source)));c.commit();c.close()
    return db,root,source,tmp_path/'journals'

def plan(library):return rename.preview(library[0],1,'Season %0S/%SN - S%0SE%0E')

def test_rename_media_sidecar_and_db(library):
    db,root,src,journals=library
    src.with_suffix('.en.srt').write_text('subtitles')
    unrelated=root/'old2.srt';unrelated.write_text('other')
    p=plan(library);result=rename.apply(db,p,[0],journals)
    assert result['files']==2 and not src.exists() and unrelated.exists()
    dest=Path(p['items'][0]['destination']);assert dest.read_bytes()==b'media'
    assert dest.with_suffix('.en.srt').read_text()=='subtitles'
    c=sqlite3.connect(db);assert c.execute('SELECT location FROM episodes').fetchone()[0]==str(dest);c.close()
    with pytest.raises(ValueError,match='changed'):rename.apply(db,p,[0],journals)

def test_stale_and_collision_leave_source(library):
    db,root,src,journals=library;p=plan(library)
    src.write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed'):rename.apply(db,p,[0],journals)
    dest=Path(p['items'][0]['destination']);dest.parent.mkdir();dest.write_bytes(b'existing')
    assert plan(library)['items'][0]['blocked']
    assert src.read_bytes()==b'changed' and dest.read_bytes()==b'existing'

def test_mid_group_failure_rolls_back(library,monkeypatch):
    db,root,src,journals=library;src.with_suffix('.srt').write_text('sub')
    p=plan(library);real=rename.move_exclusive;calls=[]
    def fail_second(a,b):
        calls.append(str(a))
        if len(calls)==2:raise OSError('simulated failure')
        return real(a,b)
    monkeypatch.setattr(rename,'move_exclusive',fail_second)
    with pytest.raises(OSError):rename.apply(db,p,[0],journals)
    assert src.exists() and src.with_suffix('.srt').exists()
    c=sqlite3.connect(db);assert c.execute('SELECT location FROM episodes').fetchone()[0]==str(src);c.close()

def test_multi_episode_file_is_one_rename(library):
    db,root,src,journals=library;c=sqlite3.connect(db)
    c.execute('INSERT INTO episodes VALUES(2,1,1,2,?,?)',('Second',str(src)));c.commit();c.close()
    p=plan(library);assert len(p['items'])==1 and 'E01E02' in p['items'][0]['destination']
    rename.apply(db,p,[0],journals)
    c=sqlite3.connect(db);assert len(set(r[0] for r in c.execute('SELECT location FROM episodes')))==1;c.close()

def test_outside_library_is_blocked(library):
    db,root,src,journals=library
    outside=root.parent/'outside.mkv';outside.write_bytes(b'outside')
    c=sqlite3.connect(db);c.execute('UPDATE episodes SET location=?',(str(outside),));c.commit();c.close()
    assert 'outside' in plan(library)['items'][0]['blocked']

def test_interrupted_journal_blocks_new_operation(library):
    import json
    db,root,src,journals=library;journals.mkdir()
    (journals/'pending.json').write_text(json.dumps({'state':'pending','show_id':1}))
    with pytest.raises(ValueError,match='interrupted'):rename.apply(db,plan(library),[0],journals)
    assert src.exists()

def test_move_never_overwrites(tmp_path):
    a=tmp_path/'a';b=tmp_path/'b';a.write_bytes(b'first');b.write_bytes(b'second')
    with pytest.raises(OSError):rename.move_exclusive(a,b)
    assert a.read_bytes()==b'first' and b.read_bytes()==b'second'

def test_media_lock_excludes_other_operation(tmp_path):
    with media_operations.exclusive(tmp_path):
        with pytest.raises(ValueError,match='Another library'):
            with media_operations.exclusive(tmp_path):pass
    with media_operations.exclusive(tmp_path):pass

def test_saved_defaults_are_typed_and_do_not_change_shows():
    c=sqlite3.connect(':memory:')
    c.executescript('CREATE TABLE settings(section,name,value,is_secret,source,updated_at,UNIQUE(section,name));CREATE TABLE quality_profiles(id);INSERT INTO quality_profiles VALUES(4);CREATE TABLE shows(id,paused);INSERT INTO shows VALUES(1,0);')
    values=show_preferences.save_defaults(c,{'quality_profile_id':'4','paused':True,'subtitles_enabled':False,'name':'ignored','location':'ignored'})
    assert show_preferences.defaults(c)==values=={'quality_profile_id':4,'paused':1,'subtitles_enabled':0}
    assert c.execute('SELECT paused FROM shows').fetchone()[0]==0
    c.close()
