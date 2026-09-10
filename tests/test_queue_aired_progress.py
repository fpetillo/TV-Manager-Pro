from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from types import SimpleNamespace
import sqlite3
from flask import Flask,request,jsonify
import episode_rules


def test_queue_uses_aired_seasons_and_sorts_before_paging(tmp_path):
    path=tmp_path/'queue.db'
    @contextmanager
    def cx():
        c=sqlite3.connect(path);c.row_factory=sqlite3.Row
        try:yield c;c.commit()
        finally:c.close()
    with cx() as c:
        c.executescript("""CREATE TABLE shows(id,name,network,quality,status,paused,search_enabled,monitor_new,imdb_id,location);
        CREATE TABLE episodes(show_id,season,episode,airdate,location,file_size,ignored,status);
        INSERT INTO shows VALUES(1,'Partial','','','',0,1,1,'',''),(2,'Future','','','',0,1,1,'',''),(3,'Missing','','','',0,1,1,'','');
        INSERT INTO episodes VALUES(1,1,1,'2020-01-01','file',1,0,'Downloaded'),(1,1,2,'2020-01-01','',0,0,'Wanted'),
        (1,2,1,'2999-01-01','',0,0,'Wanted'),(1,1,3,NULL,'',0,0,'Wanted'),(1,0,1,'2020-01-01','',0,0,'Wanted'),
        (1,1,4,'2020-01-01','',0,1,'Ignored'),(2,1,1,'2999-01-01','',0,0,'Wanted'),(3,1,1,'737203','',0,0,'Wanted');""")
    app=Flask(__name__)
    source=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')
    ns=dict(app=app,request=request,jsonify=jsonify,datetime=datetime,cx=cx,episode_rules=episode_rules,
        engine=SimpleNamespace(get_setting=lambda *a:'1',as_bool=lambda *a:True))
    exec(source[source.index('def _normalize_queue_airdate'):source.index('@app.get("/manager")')],ns)
    data=app.test_client().get('/api/show-queue?sort=aired_missing&direction=desc&limit=2').get_json()
    assert [r['id'] for r in data['results']]==[3,1] and data['has_more']
    row=data['results'][1]
    assert (row['downloaded_count'],row['episode_count'],row['missing_count'])==(1,2,1)
    assert row['missing_episode_numbers']=='S01E02'
    assert row['season_progress']==[dict(show_id=1,season=1,aired_count=2,downloaded_count=1)]
    future=app.test_client().get('/api/show-queue?q=Future').get_json()['results'][0]
    assert future['episode_count']==0 and future['season_progress']==[] and future['missing_display']=='No aired episodes'
