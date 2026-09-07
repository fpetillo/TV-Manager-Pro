import ast, re, sqlite3, tempfile
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
source=ast.parse(Path('engine.py').read_text(encoding='utf-8-sig'))
names={'_normalize_release_title','_release_prefixes_for_match','_show_match_names','_score_postprocess_show_match','_choose_postprocess_show','_scan_postprocess'}
nodes=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in names]
marker=re.compile(r'(?i)(?:^|[\s._\-\[\(])(?:S\d{1,2}E\d{1,3}|\d{1,2}x\d{1,3})(?:\b|[\s._\-\]\)])')
c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
c.executescript('CREATE TABLE shows(id,name,location,season_folders,scene_numbering); CREATE TABLE scene_mappings(show_id,alias); CREATE TABLE scene_exceptions(show_id,exception_name); INSERT INTO shows VALUES(1,"Breaking Bad",NULL,1,0);')
@contextmanager
def cx(): yield c
ns=dict(re=re,Path=Path,_EPISODE_MARKER_RE=marker,cx=cx,ops=SimpleNamespace(map_path=lambda x:x),get_setting=lambda *args:'',MEDIA_EXTS={'.mkv'},advanced=SimpleNamespace(split_multi_episode=lambda name:[(1,1)] if 'S01E01' in name else []),episode_pattern=lambda p:None)
exec(compile(ast.Module(body=nodes,type_ignores=[]),'engine.py','exec'),ns)
with tempfile.TemporaryDirectory() as folder:
    Path(folder,'Breaking.Bad.S01E01.mkv').touch();Path(folder,'Movie.2025.mkv').touch()
    for dry_run in [True,False]:
        r=ns['_scan_postprocess'](root_override=folder,dry_run=dry_run)
        assert r['matched']==1 and r['blocked']==1 and r['unmatched']==1,r
        assert 'Library folder required' in r['actions'][0]['blocked']
        assert 'No episode number' in r['unmatched_details'][0]['reason']
        assert len(list(Path(folder).glob('*.mkv')))==2
print('PASS: real scanner with missing destination blocks preview and processing; movie rejection explains reason; source files preserved')
