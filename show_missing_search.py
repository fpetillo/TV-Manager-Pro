"""Uncapped, show-scoped missing episode search using normal release rules."""
import threading
import engine
import job_center

_lock = threading.RLock()
_active = {}


def candidates(show_id, episode_id=None):
    with engine.cx() as c:
        show = c.execute("SELECT * FROM shows WHERE id=?", (show_id,)).fetchone()
        if not show:
            raise ValueError("Show not found")
        show = dict(show)
        if show.get("paused") or not show.get("search_enabled", 1):
            raise ValueError("Enable searching and unpause this show in Show Settings first.")
        rows = c.execute("""SELECT e.id FROM episodes e
            WHERE e.show_id=? AND (? IS NULL OR e.id=?) AND TRIM(COALESCE(e.location,''))=''
            AND COALESCE(e.monitored,1)=1 AND COALESCE(e.ignored,0)=0
            AND lower(COALESCE(e.status,'')) IN ('wanted','failed','unaired','skipped','unknown','')
            AND date(e.airdate) <= date('now','localtime')
            AND (?=0 OR e.season<>0)
            AND NOT EXISTS (SELECT 1 FROM downloads d WHERE d.episode_id=e.id
                AND lower(COALESCE(d.status,'')) NOT IN ('failed','error','cancelled','canceled','removed'))
            ORDER BY e.season,e.episode""", (show_id, episode_id, episode_id, int(engine.ignore_specials_from_wanted()))).fetchall()
    return [r['id'] for r in rows]


def start(show_id):
    with _lock:
        previous = job_center.get_job(_active.get(show_id, ''))
        if previous and previous.get('status') not in job_center.TERMINAL_STATUSES:
            return previous
        ids = candidates(show_id)
        if not ids:
            raise ValueError('No eligible missing episodes. Episodes must have aired and be monitored; ignored, downloaded and already queued episodes are excluded.')

        def worker(job_id):
            stats = dict(total=len(ids), searched=0, queued=0, not_found=0, skipped=0, failed=0)
            for index, eid in enumerate(ids):
                job_center.update_job(job_id, stage='Searching missing episodes',
                    message=f"Searching episode {index+1} of {len(ids)}; {stats['queued']} sent to downloader.",
                    processed=index, total=len(ids), percent=index*100//len(ids))
                try:
                    # Recheck after each search: another workflow may have queued a file.
                    if eid not in candidates(show_id, eid):
                        stats['skipped'] += 1
                        continue
                    simulation = engine.as_bool(engine.get_setting('TVManager','simulation_mode','0'))
                    result = engine.search_episode(eid, auto_grab=not simulation)
                    stats['searched'] += 1
                    if (result.get('grabbed') or {}).get('ok'):
                        stats['queued'] += 1
                    elif result.get('errors'):
                        raise ValueError('; '.join(result['errors']))
                    else:
                        stats['not_found'] += 1
                except Exception as exc:
                    stats['failed'] += 1
                    job_center.append_error(job_id, {'episode_id':eid, 'error':str(exc)})
            message = (f"{stats['queued']} sent to downloader; {stats['not_found']} not queued "
                       f"(no acceptable release or simulation mode); {stats['skipped']} skipped; {stats['failed']} failed.")
            job_center.update_job(job_id, status='complete', stage='Search finished', message=message,
                percent=100, processed=len(ids), succeeded=stats['queued'], failed=stats['failed'],
                skipped=stats['skipped'], result=stats)
            return stats

        job = job_center.run_background('show_missing_search', worker, total=len(ids),
            message=f'Searching {len(ids)} missing episodes.', meta={'show_id':show_id})
        _active[show_id] = job['job_id']
        return job
