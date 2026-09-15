from pathlib import Path
from contextlib import closing
import json
import sqlite3
import stat
import sys
import zipfile
import pytest
import archive_processing as archives
import blackhole
import episode_calendar as calendar
import process_runner


def test_archive_extraction_preserves_archive_and_reuses_verified_staging(tmp_path):
    source=tmp_path/'show.zip';staging=tmp_path/'staging'
    with zipfile.ZipFile(source,'w') as z:
        z.writestr('Season 1/Show.S01E01.mkv',b'episode');z.writestr('Season 1/Show.S01E01.srt',b'subtitle')
    paths=archives.prepare(source,staging)
    assert len(paths)==1 and paths[0].read_bytes()==b'episode'
    assert source.exists() and archives.prepare(source,staging)==paths
    archives.mark_processed(paths[0],staging)
    assert archives.prepare(source,staging)==[]


@pytest.mark.parametrize('name',['../outside.mkv','/outside.mkv','C:/outside.mkv','good/../../outside.mkv','stream:evil.mkv','CON.mkv'])
def test_archive_rejects_unsafe_names_before_writing(tmp_path,name):
    source=tmp_path/'bad.zip'
    with zipfile.ZipFile(source,'w') as z:z.writestr(name,b'unsafe')
    with pytest.raises(ValueError,match='Unsafe'):archives.prepare(source,tmp_path/'staging')
    assert not (tmp_path/'outside.mkv').exists()


def test_archive_rejects_links_duplicates_and_expansion_limit(tmp_path):
    source=tmp_path/'link.zip'
    with zipfile.ZipFile(source,'w') as z:
        link=zipfile.ZipInfo('link.mkv');link.create_system=3;link.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(link,'/outside')
    with pytest.raises(ValueError,match='links'):archives.prepare(source,tmp_path/'a')
    source=tmp_path/'duplicate.zip'
    with zipfile.ZipFile(source,'w') as z:z.writestr('Show.mkv',b'a');z.writestr('SHOW.mkv',b'b')
    with pytest.raises(ValueError,match='duplicate'):archives.prepare(source,tmp_path/'b')
    source=tmp_path/'large.zip'
    with zipfile.ZipFile(source,'w') as z:z.writestr('Show.mkv',b'12345')
    with pytest.raises(ValueError,match='limit'):archives.prepare(source,tmp_path/'c',max_bytes=4)


def test_script_runner_argument_boundaries_error_and_timeout(tmp_path):
    script=tmp_path/'helper.py';script.write_text('import sys,json;print(json.dumps(sys.argv[1:]))',encoding='utf-8')
    result=process_runner.run([sys.executable,str(script),'file with spaces.mkv','a & b'],cwd=tmp_path)
    assert json.loads(result['output'])==['file with spaces.mkv','a & b']
    with pytest.raises(ValueError,match='code 2'):process_runner.run([sys.executable,'-c','raise SystemExit(2)'],cwd=tmp_path)
    with pytest.raises(ValueError,match='timed out'):process_runner.run([sys.executable,'-c','import time;time.sleep(30)'],cwd=tmp_path,timeout=1)


def test_calendar_folding_escaping_stable_ids_and_exclusive_end():
    row={'id':3,'show_id':2,'season':1,'episode':4,'name':'é'*100+'\nInjected: value','show_name':'Show; name, title','airdate':'2026-09-15','status':'Wanted'}
    feed=calendar.feed([row])
    assert 'UID:episode-2-3@tvmanager.local' in feed and 'DTEND;VALUE=DATE:20260916' in feed
    assert 'Show\\; name\\, title' in feed and '\\nInjected: value' in feed
    assert all(len(line.encode())<=75 for line in feed.split('\r\n'))


def test_blackhole_writes_real_descriptors_and_rejects_html(tmp_path,monkeypatch):
    content=b'<nzb><file><segments><segment>message-id</segment></segments></file></nzb>'
    class Response:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def raise_for_status(self):pass
        def iter_content(self,*a):yield content
    monkeypatch.setattr(blackhole.requests,'get',lambda *a,**k:Response())
    result={'protocol':'nzb','url':'https://provider.test/file','title':'A Show'}
    path=Path(blackhole.send(result,tmp_path))
    assert path.suffix=='.nzb' and path.read_bytes()==content
    assert blackhole.send(result,tmp_path)==str(path)
    content=b'<html>Login required</html>'
    with pytest.raises(ValueError,match='NZB'):blackhole.send(result,tmp_path)
    with pytest.raises(ValueError,match='magnet'):blackhole.send(result|{'url':'magnet:?xt=urn:btih:test'},tmp_path)
    blackhole.validate(b'd4:infod4:name4:test12:piece lengthi16384e6:pieces20:12345678901234567890ee','torrent')
