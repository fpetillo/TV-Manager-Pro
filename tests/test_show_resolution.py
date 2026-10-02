import json
import sqlite3
from pathlib import Path

import pytest
import dbcore
import engine
import production
import show_preferences
import show_resolution as resolution


@pytest.fixture
def database(tmp_path, monkeypatch):
    path=tmp_path/'library.db'
    for module in (engine,production):monkeypatch.setattr(module,'DB',path)
    with dbcore.connect(path) as c:
        c.executescript('''
        CREATE TABLE shows(id INTEGER PRIMARY KEY,name,quality_profile_id,paused DEFAULT 0);
        CREATE TABLE settings(section,name,value,is_secret,source,updated_at,UNIQUE(section,name));
        CREATE TABLE show_groups(id INTEGER PRIMARY KEY,name);
        CREATE TABLE show_group_members(group_id,show_id);
        CREATE TABLE quality_profiles(id INTEGER PRIMARY KEY,min_resolution,max_resolution,cutoff_resolution,
          allow_hevc,upgrade_allowed,ignored_words,required_words,preferred_words);
        CREATE TABLE episodes(id INTEGER PRIMARY KEY,show_id,season,episode,quality,release_name,location,status);
        CREATE TABLE upgrade_candidates(id INTEGER PRIMARY KEY,episode_id,current_quality,target_quality,reason,status DEFAULT 'Candidate');
        INSERT INTO shows(id,name,quality_profile_id) VALUES(1,'First',1),(2,'Second',NULL),(3,'Third',NULL);
        INSERT INTO show_groups VALUES(1,'Favorites');
        INSERT INTO show_group_members VALUES(1,1),(1,2);
        INSERT INTO quality_profiles VALUES(1,2160,2160,2160,0,1,'bad','web','');
        INSERT INTO episodes VALUES(1,1,1,1,'720p','','existing-episode.mkv','Downloaded');
        INSERT INTO episodes VALUES(2,2,1,1,'720p','','second-episode.mkv','Downloaded');
        ''')
        show_preferences.init(c)
    return path


def preview(path, **body):
    with dbcore.connect(path) as c:return resolution.preview(c, body)


def apply(path, plan):
    with dbcore.connect(path) as c:return resolution.apply(c, plan)


def values(path):
    with dbcore.connect(path) as c:return [r[0] for r in c.execute('SELECT preferred_resolution FROM shows ORDER BY id')]


def test_scopes_and_preservation(database):
    with dbcore.connect(database) as c:
        show_preferences.save_defaults(c,{'paused':1,'metadata_language':'fr-FR'})
    single=preview(database,scope='selected',show_ids=[1],resolution='1080p')
    assert single['count']==1 and single['changed']==1
    apply(database,single)
    assert values(database)==['1080p','','']
    apply(database,preview(database,scope='group',group_id=1,resolution='720p'))
    assert values(database)==['720p','720p','']
    apply(database,preview(database,scope='all',resolution='1080p',make_default=True))
    assert values(database)==['1080p']*3
    with dbcore.connect(database) as c:
        assert show_preferences.defaults(c)==dict(paused=1,metadata_language='fr-FR',preferred_resolution='1080p')
        assert tuple(c.execute('SELECT quality,location,status FROM episodes WHERE id=1').fetchone())==('720p','existing-episode.mkv','Downloaded')
        assert c.execute('SELECT quality_profile_id FROM shows WHERE id=1').fetchone()[0]==1
        c.execute("INSERT INTO shows(id,name) VALUES(4,'New show')")
        show_preferences.apply(c,4,show_preferences.defaults(c))
        assert c.execute('SELECT preferred_resolution FROM shows WHERE id=4').fetchone()[0]=='1080p'


def test_default_only_and_clear_preserve_unrelated_preferences(database):
    apply(database,preview(database,scope='defaults',resolution='2160p'))
    assert values(database)==['','','']
    apply(database,preview(database,scope='all',resolution='1080p'))
    apply(database,preview(database,scope='selected',show_ids=[1,1,2],resolution=''))
    assert values(database)==['','','1080p']
    with dbcore.connect(database) as c:assert show_preferences.defaults(c)['preferred_resolution']=='2160p'


@pytest.mark.parametrize('body',[
    {'scope':'selected','show_ids':[],'resolution':'1080p'},
    {'scope':'selected','show_ids':[True],'resolution':'1080p'},
    {'scope':'selected','show_ids':[999],'resolution':'1080p'},
    {'scope':'group','group_id':99,'resolution':'1080p'},
    {'scope':'all','resolution':True}, {'scope':'all','resolution':'8k'},
    {'scope':'all','resolution':'1080p','make_default':'false'},
    {'scope':'filtered','resolution':'1080p'},
])
def test_invalid_input_does_not_mutate(database,body):
    with pytest.raises(ValueError):preview(database,**body)
    assert values(database)==['','','']


@pytest.mark.parametrize('change',[
    "UPDATE shows SET preferred_resolution='720p' WHERE id=1",
    "DELETE FROM show_group_members WHERE show_id=2",
    "INSERT INTO show_group_members VALUES(1,3)",
    "INSERT INTO settings VALUES('ShowDefaults','preferences','{\"paused\":1}',0,'test','now')",
])
def test_changed_review_is_rejected(database,change):
    plan=preview(database,scope='group',group_id=1,resolution='1080p',make_default=True)
    with dbcore.connect(database) as c:c.execute(change)
    before=values(database)
    with pytest.raises(ValueError,match='changed after'):apply(database,plan)
    assert values(database)==before


def test_large_all_scope_and_membership_change(database):
    with dbcore.connect(database) as c:
        c.executemany('INSERT INTO shows(id,name) VALUES(?,?)',[(i,f'Show {i}') for i in range(4,1205)])
    plan=preview(database,scope='all',resolution='1080p')
    assert plan['count']==1204
    assert apply(database,plan)['changed']==1204
    with dbcore.connect(database) as c:c.execute("INSERT INTO shows(id,name) VALUES(1205,'Added')")
    with pytest.raises(ValueError,match='changed after'):apply(database,plan)


@pytest.mark.parametrize('title,expected',[
    ('Show.S01E01.1080p.WEB-DL',True),('Show.S01E01.720p.WEB',False),
    ('Show.S01E01.2160p.WEB',False),('Show.S01E01.4K.WEB',False),
    ('Show.S01E01.1080i.WEB',False),('Show.S01E01.WEB',False),
    ('Show.S01E01.1080p.WEB.x265',False),('Show.S01E01.1080p.BluRay',False),
    ('Show.S01E01.bad.1080p.WEB',False),
])
def test_resolution_overrides_only_profile_bounds(database,title,expected):
    show={'quality_profile_id':1,'preferred_resolution':'1080p'}
    _,reason=engine.score_release(title,show)
    assert (reason is None)==expected
    if expected:
        assert engine.score_release(title,{'quality_profile_id':1})[1] is not None


@pytest.mark.parametrize('title,selected',[('Show.4k.WEB','2160p'),('Show.480p','sd'),('Show.576p','sd'),('Show.DVDRip','sd')])
def test_other_resolution_choices(title,selected):
    assert resolution.rejection(title,selected) is None


def test_upgrade_targets_respect_override_and_profile_switch(database):
    apply(database,preview(database,scope='all',resolution='1080p'))
    result=production.plan_upgrades()
    assert result['count']==2 and {r['target_quality'] for r in result['results']}=={'1080p'}
    with dbcore.connect(database) as c:c.execute('UPDATE quality_profiles SET upgrade_allowed=0')
    assert production.plan_upgrades()['count']==1


def test_options_reject_bad_single_show_value():
    with pytest.raises(ValueError):show_preferences.options({'preferred_resolution':'1081p'})
    assert show_preferences.options({'preferred_resolution':'1080p'})=={'preferred_resolution':'1080p'}


@pytest.mark.parametrize('kind',['episode','season_pack'])
def test_cached_result_cannot_bypass_changed_resolution(database,monkeypatch,kind):
    import release
    monkeypatch.setattr(release,'DB',database)
    def forbidden_handoff(*args):
        pytest.fail('A mismatched release must never reach the downloader')
    monkeypatch.setattr(engine,'handoff_adapter',forbidden_handoff)
    with dbcore.connect(database) as c:
        c.executescript('''
        CREATE TABLE search_results(id INTEGER PRIMARY KEY,episode_id,title,rejected_reason);
        CREATE TABLE season_pack_searches(id INTEGER PRIMARY KEY,show_id,season,title);
        INSERT INTO search_results VALUES(1,2,'Second.S01E01.720p.WEB',NULL);
        INSERT INTO season_pack_searches VALUES(1,2,1,'Second.S01.720p.WEB');
        ''')
    apply(database,preview(database,scope='selected',show_ids=[2],resolution='1080p'))
    with pytest.raises(ValueError,match='no longer matches.*1080p'):
        (engine._grab_result if kind=='episode' else release.grab_season_pack)(1)
    with dbcore.connect(database) as c:
        assert c.execute('SELECT status FROM episodes WHERE id=2').fetchone()[0]=='Downloaded'
