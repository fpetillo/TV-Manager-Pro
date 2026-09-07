import ast, sqlite3, sys
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from library_destinations import library_roots,show_destination,rebase_episode_location
roots=r'1|\\nas\TV|D:\TV'
assert library_roots(roots)[1]==r'D:\TV'
assert show_destination(roots,r'\\nas\TV','Breaking Bad')==r'\\nas\TV\Breaking Bad'
assert show_destination('0|/media/tv','/media/tv','Friends')=='/media/tv/Friends'
for folder in ['../bad','..','CON','bad/name','bad\\name','']:
    try: show_destination(roots,r'D:\TV',folder)
    except ValueError: pass
    else: raise AssertionError(folder)
source=ast.parse(Path('app.py').read_text(encoding='utf-8-sig'))
names={'add','api_trakt_add_show','requested_show_destination','api_show_destination'}
nodes=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in names]
for n in nodes:n.decorator_list=[]
c=sqlite3.connect(':memory:',isolation_level=None);c.row_factory=sqlite3.Row
c.execute('CREATE TABLE settings(section,name,value)')
c.execute('INSERT INTO settings VALUES(?,?,?)',('General','root_dirs',roots))
c.execute('CREATE TABLE shows(id INTEGER PRIMARY KEY,tmdb_id,imdb_id,name,original_name,first_air_date,overview,poster,vote_average,status,location,season_folders,trakt_id,trakt_slug,tvdb_id,network,quality,monitor_new,search_enabled,added_at,metadata_provider,episode_order)')
@contextmanager
def cx():
    with c:yield c
body={}
ns=dict(cx=cx,request=SimpleNamespace(get_json=lambda **kw:body),jsonify=lambda **kw:kw,engine=SimpleNamespace(get_setting=lambda *args:roots),show_destination=show_destination,rebase_episode_location=rebase_episode_location,datetime=datetime,existing=lambda c,**kw:False)
exec(compile(ast.Module(body=nodes,type_ignores=[]),'app.py','exec'),ns)
body.update(name='Breaking Bad');assert ns['add']()[1]==400
body.update(library_root=r'D:\TV',folder_name='Breaking Bad');assert ns['add']()[1]==201
row=c.execute('SELECT * FROM shows').fetchone();assert row['location']==r'D:\TV\Breaking Bad' and row['season_folders']==1
body.clear();body.update(name='Friends',library_root=r'\\nas\TV',folder_name='Friends');assert ns['api_trakt_add_show']()['created']
row=c.execute('SELECT * FROM shows WHERE name="Friends"').fetchone();assert row['location']==r'\\nas\TV\Friends'
c.execute('INSERT INTO shows(name) VALUES("Missing")');sid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
body.clear();body.update(library_root=r'D:\TV',folder_name='Missing',previous_location='');assert ns['api_show_destination'](sid)['location']==r'D:\TV\Missing'
assert ns['api_show_destination'](sid)[1]==409
assert ns['api_show_destination'](999)[1]==404
c.execute('CREATE TABLE episodes(id INTEGER PRIMARY KEY,show_id,location)')
c.execute('INSERT INTO episodes(show_id,location) VALUES(?,?)',(sid,r'D:\TV\Missing\Season 01\episode.mkv'))
c.execute('INSERT INTO episodes(show_id,location) VALUES(?,?)',(sid,r'D:\TV\Missing Other\unrelated.mkv'))
body.update(previous_location=r'D:\TV\Missing',folder_name='New',update_episode_paths=True)
assert ns['api_show_destination'](sid)['episode_paths_updated']==1
assert c.execute('SELECT location FROM episodes WHERE id=1').fetchone()[0]==r'D:\TV\New\Season 01\episode.mkv'
assert c.execute('SELECT location FROM episodes WHERE id=2').fetchone()[0]==r'D:\TV\Missing Other\unrelated.mkv'
body.update(previous_location=r'D:\TV\New',folder_name='Future',update_episode_paths=False)
assert ns['api_show_destination'](sid)['episode_paths_updated']==0
assert c.execute('SELECT location FROM episodes WHERE id=1').fetchone()[0]==r'D:\TV\New\Season 01\episode.mkv'
assert rebase_episode_location('/tv/Show/a.mkv','/tv/Show','/new/Show')=='/new/Show/a.mkv'
assert rebase_episode_location('/tv/Show2/a.mkv','/tv/Show','/new/Show')=='/tv/Show2/a.mkv'
print('PASS: configured roots/default, UNC/Windows/POSIX paths, invalid names, mandatory destination, both add routes persist path, repair and relocation guard')
