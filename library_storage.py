"""Nonblocking, bounded disk-space checks for configured library roots."""
import shutil
import threading
import time
from datetime import datetime, timezone

_LOCK=threading.Lock()
_CACHE={}
_RUNNING=set()
_MAX_WORKERS=4
_TTL=60


def storage_status(roots, map_path=lambda p:p):
    rows=[]
    with _LOCK:
        for root in roots:
            mapped=map_path(root)
            key=(root,mapped)
            entry=_CACHE.get(key)
            if key not in _RUNNING and (entry is None or time.monotonic()-entry['_time']>=_TTL) and len(_RUNNING)<_MAX_WORKERS:
                _RUNNING.add(key)
                _CACHE[key]={'root':root,'mapped_path':mapped,'status':'checking','_time':time.monotonic()}
                threading.Thread(target=_check,args=(key,),daemon=True).start()
            entry=dict(_CACHE.get(key) or {'root':root,'mapped_path':mapped,'status':'queued'})
            if entry['status']=='checking' and time.monotonic()-entry['_time']>8:
                entry['status']='slow'
                entry['message']='Storage is slow to respond. Other available results are shown.'
            entry.pop('_time',None)
            rows.append(entry)
    return rows


def _check(key):
    root,mapped=key
    result={'root':root,'mapped_path':mapped,'checked_at':datetime.now(timezone.utc).isoformat()}
    try:
        usage=shutil.disk_usage(mapped)
        result.update(status='ready',total=usage.total,used=usage.used,free=usage.free,percent_used=round(100*usage.used/usage.total,1) if usage.total else 0)
    except OSError as exc:
        result.update(status='unavailable',message=str(exc))
    finally:
        with _LOCK:
            result['_time']=time.monotonic()
            _CACHE[key]=result
            _RUNNING.discard(key)
