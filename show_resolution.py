"""Resolution preferences and reviewed library-wide changes (no media operations)."""
import hashlib
import json
import re

CHOICES = {'': 'Use quality profile', 'sd': 'SD (480p / 576p)',
           '720p': '720p', '1080p': '1080p', '2160p': '2160p / 4K'}


def validate(value):
    if not isinstance(value, str) or value not in CHOICES:
        raise ValueError('Choose SD, 720p, 1080p, 2160p / 4K, or Use quality profile.')
    return value


def detected(title):
    text = str(title or '').lower()
    match = re.search(r'(?<![a-z0-9])(2160p|1080p|1080i|720p|576p|576i|480p|480i|4k)(?![a-z0-9])', text)
    if match:
        value = match[1]
        return '2160p' if value == '4k' else 'sd' if value[:3] in {'480', '576'} else value
    if re.search(r'(?<![a-z0-9])(sdtv|pdtv|dvdrip)(?![a-z0-9])', text):
        return 'sd'
    return ''


def rejection(title, preference):
    if not preference:
        return None
    actual = detected(title)
    if actual != preference:
        return f"Show requires {CHOICES[preference]}; release is {CHOICES.get(actual, actual) if actual else 'unknown resolution'}."
    return None


def target(preference):
    return {'sd': 480, '720p': 720, '1080p': 1080, '2160p': 2160}.get(preference, 0)


def preview(c, body):
    import show_preferences
    if not isinstance(body, dict):
        raise ValueError('Enter a resolution change.')
    resolution = validate(body.get('resolution'))
    scope = body.get('scope')
    if scope not in {'selected', 'group', 'all', 'defaults'}:
        raise ValueError('Choose selected shows, a group, all shows, or new shows only.')
    make_default = body.get('make_default', False)
    if not isinstance(make_default, bool):
        raise ValueError('Invalid new-show default choice.')
    selection = {'scope': scope, 'resolution': resolution, 'make_default': make_default or scope == 'defaults'}
    sql = "SELECT id,name,COALESCE(preferred_resolution,'') preferred_resolution FROM shows"
    if scope == 'group':
        gid = body.get('group_id')
        if type(gid) is not int or not c.execute('SELECT 1 FROM show_groups WHERE id=?', (gid,)).fetchone():
            raise ValueError('Choose an existing show group.')
        selection['group_id'] = gid
        rows = c.execute(sql + ' WHERE id IN (SELECT show_id FROM show_group_members WHERE group_id=?) ORDER BY id', (gid,)).fetchall()
    elif scope == 'defaults':
        rows = []
    else:
        rows = c.execute(sql + ' ORDER BY id').fetchall()
        if scope == 'selected':
            ids = body.get('show_ids')
            if not isinstance(ids, list) or not ids or len(ids) > 50000 or any(type(i) is not int or i <= 0 for i in ids):
                raise ValueError('Select at least one show.')
            ids = sorted(set(ids))
            selected = set(ids)
            rows = [r for r in rows if r['id'] in selected]
            if len(rows) != len(ids):
                raise ValueError('A selected show no longer exists. Refresh the list.')
            selection['show_ids'] = ids
    if not rows and scope != 'defaults':
        raise ValueError('There are no shows in this selection.')
    defaults = show_preferences.defaults(c)
    signature = {'shows': [dict(r) for r in rows],
                 'defaults': defaults if selection['make_default'] else None}
    digest = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    return {'selection': selection, 'fingerprint': digest, 'count': len(rows),
            'changed': sum(r['preferred_resolution'] != resolution for r in rows),
            'label': CHOICES[resolution], 'sample': [r['name'] for r in rows[:8]],
            'ids': [r['id'] for r in rows]}


def apply(c, plan):
    import show_preferences
    c.execute('BEGIN IMMEDIATE')
    current = preview(c, plan['selection'])
    if current['fingerprint'] != plan['fingerprint']:
        raise ValueError('Shows or defaults changed after the review. Review the change again.')
    resolution = current['selection']['resolution']
    c.executemany('UPDATE shows SET preferred_resolution=? WHERE id=?',
                  [(resolution, sid) for sid in current['ids']])
    if current['selection']['make_default']:
        show_preferences.save_defaults(c, {**show_preferences.defaults(c), 'preferred_resolution': resolution})
    return {'ok': True, 'count': current['count'], 'changed': current['changed'],
            'label': current['label'], 'default_saved': current['selection']['make_default']}
