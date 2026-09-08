import sys,time,threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import library_storage as storage
release=threading.Event()
def disk(path):
    if path=='slow': release.wait(3)
    if path=='missing': raise OSError('Not reachable')
    return SimpleNamespace(total=1000,used=600,free=400)
with patch.object(storage.shutil,'disk_usage',side_effect=disk) as check:
    begin=time.monotonic();rows=storage.storage_status(['slow','ok','missing']);assert time.monotonic()-begin<0.5
    for _ in range(100):
        rows=storage.storage_status(['slow','ok','missing'])
        if rows[1]['status']=='ready' and rows[2]['status']=='unavailable':break
        time.sleep(.01)
    assert rows[1]['free']==400 and rows[1]['percent_used']==60
    assert rows[2]['status']=='unavailable' and 'free' not in rows[2]
    before=check.call_count
    storage.storage_status(['slow','ok','missing']);assert check.call_count==before
    with storage._LOCK:storage._CACHE[('slow','slow')]['_time']-=10
    assert storage.storage_status(['slow'])[0]['status']=='slow'
    release.set()
    for _ in range(100):
        if storage.storage_status(['slow'])[0]['status']=='ready':break
        time.sleep(.01)
    assert storage.storage_status(['slow'])[0]['status']=='ready'
print('PASS: nonblocking storage, correct capacity, unreachable status, cached checks, slow status and recovery')
