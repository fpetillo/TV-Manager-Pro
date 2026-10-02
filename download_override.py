"""Review a deliberate duplicate submission without erasing download history."""
import hashlib
import json


class DuplicateDownload(ValueError):
    pass


def recovery(error, result_id):
    return {'error': str(error), 'code': 'duplicate_download' if isinstance(error, DuplicateDownload) else 'download_error',
            'force_available': isinstance(error, DuplicateDownload), 'result_id': result_id,
            'review_url': '/download-center'}


def preview(c, result_id):
    result=c.execute('''SELECT sr.*,e.show_id,e.season,e.episode,s.name show_name
        FROM search_results sr JOIN episodes e ON e.id=sr.episode_id
        JOIN shows s ON s.id=e.show_id WHERE sr.id=?''',(result_id,)).fetchone()
    if not result:raise ValueError('Search result no longer exists. Search the episode again.')
    result=dict(result)
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'acquisition_reservations' in tables and c.execute('SELECT 1 FROM acquisition_reservations WHERE episode_id=?',(result['episode_id'],)).fetchone():
        raise ValueError('A download handoff is still running or unresolved. Review it in Download Center before forcing another download.')
    downloads=[dict(r) for r in c.execute('''SELECT * FROM downloads WHERE episode_id=?
        AND (lower(status) IN ('queued','downloading','downloaded','importing')
        OR (search_result_id=? AND lower(status)='completed')) ORDER BY id''',(result['episode_id'],result_id))]
    packs=[dict(r) for r in c.execute('''SELECT * FROM season_pack_downloads WHERE show_id=? AND season=?
        AND lower(status) IN ('queued','downloading','downloaded','importing') ORDER BY id''',
        (result['show_id'],result['season']))] if 'season_pack_downloads' in tables else []
    # Progress polling must not expire an otherwise unchanged confirmation.
    stable=lambda rows:[{k:v for k,v in row.items() if k not in {'progress','updated_at'}} for row in rows]
    signature={'result':result,'downloads':stable(downloads),'packs':stable(packs)}
    digest=hashlib.sha256(json.dumps(signature,sort_keys=True,default=str).encode()).hexdigest()
    conflicts=[{'kind':'episode','id':r['id'],'client':r.get('client') or '',
                'title':r.get('release_name') or '', 'status':r['status']} for r in downloads]
    conflicts += [{'kind':'season pack','id':r['id'],'client':r.get('client') or '',
                   'title':r.get('title') or '', 'status':r['status']} for r in packs]
    return {'result_id':result_id,'fingerprint':digest,'title':result['title'],
            'show_name':result['show_name'],'season':result['season'],'episode':result['episode'],
            'conflicts':conflicts}


def validate(c, result_id, review):
    current=preview(c,result_id)
    if review.get('result_id')!=result_id or review.get('fingerprint')!=current['fingerprint']:
        raise ValueError('Download state changed after review. Review Force Download again.')
    return current
