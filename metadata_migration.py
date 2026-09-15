"""Reviewed source/order changes preserve episode IDs, file locations and history."""
from datetime import date
import hashlib
import json
import re
import uuid

import dbcore
import episode_dates


def snapshot(c, show_id):
    row = c.execute('SELECT * FROM shows WHERE id=?', (show_id,)).fetchone()
    if not row:
        raise ValueError('Show not found')
    return {'show': dict(row), 'episodes': [dict(r) for r in c.execute('SELECT * FROM episodes WHERE show_id=? ORDER BY id', (show_id,))]}


def digest(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()


def active(c, show_id):
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'downloads' in tables and c.execute("SELECT 1 FROM downloads d JOIN episodes e ON e.id=d.episode_id WHERE e.show_id=? AND lower(d.status) IN ('queued','downloading','downloaded','importing') LIMIT 1", (show_id,)).fetchone():
        raise ValueError('Finish or resolve active downloads for this show before changing its metadata source or order.')
    if 'season_pack_downloads' in tables and c.execute("SELECT 1 FROM season_pack_downloads WHERE show_id=? AND lower(status) IN ('queued','downloading','downloaded','importing') LIMIT 1", (show_id,)).fetchone():
        raise ValueError('Finish or resolve this show’s active season packs before changing metadata.')
    if 'acquisition_reservations' in tables and c.execute('SELECT 1 FROM acquisition_reservations a JOIN episodes e ON e.id=a.episode_id WHERE e.show_id=? LIMIT 1', (show_id,)).fetchone():
        raise ValueError('Resolve this show’s pending downloader handoffs before changing metadata.')


def payload(db, show, target):
    provider = target.get('provider')
    order = target.get('order', 'official')
    try:
        remote_id = int(target.get('remote_id'))
    except (TypeError, ValueError):
        raise ValueError('Enter the show ID from the chosen metadata provider.') from None
    if remote_id <= 0 or provider not in {'tvdb', 'tmdb'} or order not in {'official', 'dvd'}:
        raise ValueError('Choose a supported metadata source, show ID and episode order.')
    if order == 'dvd' and provider != 'tvdb':
        raise ValueError('DVD order requires TVDB.')
    if provider == 'tvdb':
        import tvdb_client
        info, seasons = tvdb_client.show_payload(dict(show, tvdb_id=remote_id, episode_order=order), db)
    else:
        import tmdb_client
        language = show.get('metadata_language') or 'en-US'
        info = tmdb_client.get(f'/tv/{remote_id}', params={'language': language, 'append_to_response': 'external_ids'}, db_path=db)
        seasons = []
        for season in info.get('seasons', []):
            number = season.get('season_number')
            if number is not None:
                seasons.append((int(number), tmdb_client.get(f'/tv/{remote_id}/season/{number}', params={'language': language}, db_path=db)))
    episodes, ids, numbers = [], set(), set()
    for season, data in seasons:
        for ep in data.get('episodes', []):
            identity, number = ep.get('id'), ep.get('episode_number')
            if not identity or number is None:
                raise ValueError('Metadata contains an episode without a stable ID or number.')
            position = (int(season), int(number))
            if min(position) < 0 or identity in ids or position in numbers:
                raise ValueError('Metadata contains duplicate or invalid episode identities or numbers.')
            ids.add(identity); numbers.add(position)
            image = ep.get('image') if provider == 'tvdb' else ('https://image.tmdb.org/t/p/w500' + ep['still_path'] if ep.get('still_path') else None)
            episodes.append({'remote_id': identity, 'season': position[0], 'episode': position[1],
                             'name': ep.get('name') or '', 'airdate': episode_dates.normalize(ep.get('air_date')),
                             'overview': ep.get('overview') or '', 'still_url': image})
    if not episodes:
        raise ValueError('Metadata source returned no episodes; the existing library was preserved.')
    return {'provider': provider, 'order': order, 'remote_id': remote_id,
            'name': info.get('name') or show['name'], 'episodes': episodes,
            'external_ids': info.get('external_ids') or {}}


def match(existing, target):
    field = target['provider'] + '_episode_id'
    remote = target['episodes']
    def title(text):
        return re.sub(r'[^\w]+', '', str(text or '').casefold())
    suggestions = []
    for old in existing:
        candidates = [i for i, ep in enumerate(remote) if old.get(field) and str(ep['remote_id']) == str(old[field])]
        reason = 'Provider episode ID'
        if not candidates and not old.get(field):
            candidates = [i for i, ep in enumerate(remote) if title(old.get('name')) and title(old.get('name')) == title(ep['name']) and episode_dates.normalize(old.get('airdate')) == ep['airdate']]
            reason = 'Matching title and air date — review before applying'
        suggestions.append({'episode_id': old['id'], 'season': old['season'], 'episode': old['episode'],
                            'name': old.get('name') or '', 'location': old.get('location') or '',
                            'target_index': candidates[0] if len(candidates) == 1 else None,
                            'reason': reason if len(candidates) == 1 else 'Choose the corresponding episode'})
    used = {}
    for suggestion in suggestions:
        index = suggestion['target_index']
        if index is not None:
            used.setdefault(index, []).append(suggestion)
    for group in used.values():
        if len(group) > 1:
            for suggestion in group:
                suggestion.update(target_index=None, reason='Multiple existing episodes match; choose each episode explicitly')
    return suggestions


def preview(db, show_id, target):
    with dbcore.connect(db, readonly=True) as c:
        active(c, show_id)
        state = snapshot(c, show_id)
    remote = payload(db, state['show'], target)
    rows = match(state['episodes'], remote)
    return {'show_id': show_id, 'show_name': state['show']['name'], 'revision': digest(state),
            'target': remote, 'matches': rows,
            'unmatched': sum(r['target_index'] is None for r in rows)}


def apply(db, plan, choices):
    import show_preferences
    if not isinstance(choices, dict):
        raise ValueError('Review every existing episode before applying the change.')
    target = plan['target']; episodes = target['episodes']; selected = {}
    for row in plan['matches']:
        choice = choices.get(str(row['episode_id']), row['target_index'])
        if type(choice) is not int or not 0 <= choice < len(episodes):
            raise ValueError('Every existing episode needs a corresponding episode in the new source/order.')
        if choice in selected.values():
            raise ValueError('Two existing episodes cannot use the same new episode. Review the matches.')
        selected[row['episode_id']] = choice
    with dbcore.connect(db) as c:
        c.execute('BEGIN IMMEDIATE')
        active(c, plan['show_id'])
        before = snapshot(c, plan['show_id'])
        if digest(before) != plan['revision']:
            raise ValueError('The show or its episodes changed after preview. Preview again before applying.')
        show = before['show']; show_id = show['id']
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        # Two-phase renumbering handles swaps without violating (show,season,episode).
        for eid in selected:
            c.execute('UPDATE episodes SET season=-1,episode=? WHERE id=?', (-int(eid), eid))
        id_field = target['provider'] + '_episode_id'
        other_field = 'tmdb_episode_id' if target['provider'] == 'tvdb' else 'tvdb_episode_id'
        for eid, index in selected.items():
            ep = episodes[index]
            c.execute(f'''UPDATE episodes SET season=?,episode=?,name=?,airdate=?,overview=?,still_url=?,
                {id_field}=?,{other_field}=NULL,scene_season=NULL,scene_episode=NULL,absolute_number=NULL,
                metadata_updated_at=CURRENT_TIMESTAMP WHERE id=?''',
                (ep['season'], ep['episode'], ep['name'], ep['airdate'], ep['overview'], ep['still_url'], ep['remote_id'], eid))
        added = 0
        for index, ep in enumerate(episodes):
            if index in selected.values():
                continue
            status = show_preferences.initial_episode_status(show, ep['airdate'], date.today().isoformat())
            c.execute(f'''INSERT INTO episodes(show_id,season,episode,name,airdate,overview,still_url,{id_field},status,metadata_updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''',
                (show_id, ep['season'], ep['episode'], ep['name'], ep['airdate'], ep['overview'], ep['still_url'], ep['remote_id'], status))
            added += 1
        source_id = 'tvdb_id' if target['provider'] == 'tvdb' else 'tmdb_id'
        other_id = 'tmdb_id' if target['provider'] == 'tvdb' else 'tvdb_id'
        c.execute(f'''UPDATE shows SET metadata_provider=?,episode_order=?,{source_id}=?,{other_id}=NULL,
            name=COALESCE(NULLIF(name_override,''),?),scene_numbering=0 WHERE id=?''',
            (target['provider'], target['order'], target['remote_id'], target['name'], show_id))
        if 'imdb_id' in show:
            c.execute('UPDATE shows SET imdb_id=? WHERE id=?',(target.get('external_ids',{}).get('imdb_id'),show_id))
        for table in ('xem_mappings', 'xem_refresh'):
            if table in tables:
                c.execute(f'DELETE FROM {table} WHERE show_id=?', (show_id,))
        if 'scene_mappings' in tables:
            c.execute('DELETE FROM scene_mappings WHERE show_id=? AND season IS NOT NULL AND episode IS NOT NULL', (show_id,))
        if 'search_results' in tables:
            c.execute("UPDATE search_results SET rejected_reason='Metadata source or episode order changed',status='Rejected' WHERE episode_id IN (SELECT id FROM episodes WHERE show_id=?) AND status='Found'", (show_id,))
        c.execute('''CREATE TABLE IF NOT EXISTS metadata_migrations(id TEXT PRIMARY KEY,show_id INTEGER,
            previous_json TEXT NOT NULL,target_json TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        migration_id = uuid.uuid4().hex
        c.execute('INSERT INTO metadata_migrations(id,show_id,previous_json,target_json) VALUES(?,?,?,?)',
                  (migration_id, show_id, json.dumps(before), json.dumps(target)))
    return {'ok': True, 'migration_id': migration_id, 'updated': len(selected), 'added': added,
            'message': 'Metadata updated. Episode history and existing file paths were preserved. Review scene numbering before enabling it again.'}
