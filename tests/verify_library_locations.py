import sys,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import library_locations as lib
c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
c.executescript('CREATE TABLE settings(section,name,value,is_secret,source,updated_at); CREATE TABLE shows(id INTEGER PRIMARY KEY,name,location);')
lib.change(c,dict(action='add',new_path=r'D:\TV'))
lib.change(c,dict(action='add',new_path=r'\\nas\share\TV'))
assert lib.locations(c)[0]['is_default']
lib.change(c,dict(action='default',path=r'\\nas\share\TV'))
assert lib.locations(c)[1]['is_default']
c.execute('INSERT INTO shows(name,location) VALUES(?,?)',('Friends',r'd:\tv\Friends'))
for action in ['edit','remove']:
    try:lib.change(c,dict(action=action,path=r'D:\TV',new_path=r'E:\TV'))
    except lib.LocationInUse as exc: assert exc.shows[0]['name']=='Friends'
    else:raise AssertionError('Allowed a used root to be removed')
assert not lib.contains(r'D:\TV',r'D:\TV Other\Show')
assert lib.contains(r'D:\TV',r'd:\tv')
try:lib.change(c,dict(action='add',new_path='d:/TV/'))
except ValueError:pass
else:raise AssertionError('Duplicate allowed')
lib.change(c,dict(action='edit',path=r'\\nas\share\TV',new_path=r'\\nas\share\TV New'))
assert lib.locations(c)[1]['is_default']
lib.change(c,dict(action='remove',path=r'\\nas\share\TV New'))
assert lib.locations(c)[0]['is_default']
c.execute('DELETE FROM shows')
lib.change(c,dict(action='remove',path=r'D:\TV'))
assert lib.locations(c)==[]
for p in ['relative','D:relative','/tv|/bad','/tv\ninvalid']:
    try:lib.validate_root(p)
    except ValueError:pass
    else:raise AssertionError(p)
print('PASS: add/edit/default/remove, used-root protection and affected shows, normalized duplicates, boundary matching, default reassignment, empty list, invalid paths')
