"""Editable imported providers without discarding SickChill's extended fields."""
import hashlib
import re
import time

import indexer_client

MASK = '••••••••'


def parse(raw, order=''):
    ordering = {v: i for i, v in enumerate(order.lower().split())}
    rows = []
    for index, entry in enumerate(str(raw or '').strip().strip('"').split('!!!')):
        parts = entry.split('|')
        if len(parts) < 2:
            continue
        def field(n, default=''):
            return parts[n].strip() if len(parts) > n else default
        name = field(0)
        slug = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
        rows.append({'id': f'imported-{index}', 'revision': hashlib.sha256(entry.encode()).hexdigest(),
                     'name': name, 'url': field(1), 'api_key': field(2), 'categories': field(3),
                     'enabled': field(4, '1').lower() in {'1', 'true'},
                     'search_mode': field(5, 'episode'), 'search_fallback': field(6, '0') == '1',
                     'enable_daily': field(7, '1') == '1', 'enable_backlog': field(8, '1') == '1',
                     'priority': ordering.get(slug, 9999), 'protocol': 'nzb'})
    return sorted(rows, key=lambda p: (not p['enabled'], p['priority'], p['name'].lower()))


def eligible(provider, purpose='manual'):
    if not provider.get('enabled', True):
        return False
    field = {'recent': 'enable_daily', 'backlog': 'enable_backlog'}.get(purpose)
    return not field or bool(provider.get(field, True))


def listing():
    import engine, advanced, ops
    health = {x['provider']: x for x in ops.provider_health()}
    providers = engine.parse_newznab()
    for row in advanced.provider_defs():
        row.update(id=f"custom-{row['id']}", origin='Custom')
        providers.append(row)
    out = []
    for provider in providers:
        item = dict(provider)
        item['origin'] = item.get('origin', 'Imported from SickChill')
        item['has_api_key'] = bool(item.pop('api_key', ''))
        item['health'] = health.get(item['name'], {})
        try:
            indexer_client.endpoint(item['url'])
            item['configuration_issue'] = ''
        except ValueError as error:
            item['configuration_issue'] = str(error)
        out.append(item)
    return out


def raw_provider(identity):
    import engine, advanced
    if identity.startswith('imported-'):
        row = next((p for p in engine.parse_newznab() if p['id'] == identity), None)
    elif identity.startswith('custom-'):
        with advanced.cx() as c:
            item = c.execute('SELECT * FROM provider_definitions WHERE id=?', (identity[7:],)).fetchone()
        row = dict(item) if item else None
    else:
        row = None
    if not row:
        raise ValueError('Provider no longer exists. Refresh the list.')
    return row


def validate(body, validate_url=True):
    data = dict(body)
    for key in ('name', 'url', 'categories', 'api_key'):
        value = str(data.get(key, '')).strip()
        if len(value) > 2048 or any(c in value for c in '|!\r\n\x00'):
            raise ValueError('Provider fields contain an unsupported character or are too long.')
        data[key] = value
    if not data['name'] or not data['url']:
        raise ValueError('Enter a provider name and API address.')
    if validate_url:
        indexer_client.endpoint(data['url'])
    if data.get('protocol', 'newznab') not in {'nzb', 'newznab', 'torznab'}:
        raise ValueError('Choose Newznab or Torznab.')
    if data['categories'] and not re.fullmatch(r'\d+(?:,\s*\d+)*', data['categories']):
        raise ValueError('Use comma-separated numeric category IDs, or leave categories empty.')
    for key in ('enabled', 'enable_daily', 'enable_backlog'):
        value = data.get(key, True)
        if value not in (True, False, 0, 1, '0', '1'):
            raise ValueError('Choose On or Off for provider switches.')
        data[key] = value in (True, 1, '1')
    for key in ('priority', 'minimum_seeders'):
        try:
            data[key] = int(data.get(key, 100 if key == 'priority' else 0))
        except (ValueError, TypeError):
            raise ValueError('Enter whole numbers for priority and minimum seeders.') from None
        if not 0 <= data[key] <= 100000:
            raise ValueError('Priority and minimum seeders must be between 0 and 100000.')
    return data


def unique_name(c, name, identity=None):
    imported=c.execute("SELECT value FROM settings WHERE lower(section)='newznab' AND lower(name)='newznab_data'").fetchone()
    names=[(p['id'],p['name']) for p in parse(imported['value'] if imported else '')]
    names.extend((f"custom-{r['id']}",r['name']) for r in c.execute('SELECT id,name FROM provider_definitions'))
    if any(key!=identity and other.casefold()==name.casefold() for key,other in names):
        raise ValueError('Another provider already uses that name. Use a distinct name for separate connections.')


def save(identity, body):
    import engine, advanced
    old = raw_provider(identity)
    merged = dict(old, **body)
    if body.get('api_key', MASK) == MASK:
        merged['api_key'] = old.get('api_key', '')
    # Disabling a bad imported address must still be possible.
    data = validate(merged, validate_url=merged.get('enabled') not in (False, 0, '0'))
    if identity.startswith('custom-'):
        data['id'] = int(identity[7:])
        return advanced.save_provider(data)
    index = int(identity[9:])
    with engine.cx() as c:
        c.execute('BEGIN IMMEDIATE')
        unique_name(c,data['name'],identity)
        row = c.execute("SELECT value FROM settings WHERE lower(section)='newznab' AND lower(name)='newznab_data'").fetchone()
        chunks = row['value'].strip().strip('"').split('!!!')
        if index >= len(chunks) or hashlib.sha256(chunks[index].encode()).hexdigest() != body.get('revision'):
            raise ValueError('Provider changed since this form opened. Refresh and review it again.')
        parts = chunks[index].split('|')
        while len(parts) < 9:
            parts.append(('episode' if len(parts) == 5 else '0') if len(parts) < 7 else '1')
        parts[:5] = [data['name'], data['url'], data['api_key'], data['categories'], str(int(data['enabled']))]
        parts[7:9] = [str(int(data['enable_daily'])), str(int(data['enable_backlog']))]
        chunks[index] = '|'.join(parts)
        c.execute("UPDATE settings SET value=?,is_secret=1,updated_at=CURRENT_TIMESTAMP WHERE lower(section)='newznab' AND lower(name)='newznab_data'", ('!!!'.join(chunks),))
    return identity


def remove(identity, revision=''):
    import engine, advanced
    raw_provider(identity)
    if identity.startswith('custom-'):
        advanced.delete_provider(int(identity[7:]))
        return
    index = int(identity[9:])
    with engine.cx() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute("SELECT value FROM settings WHERE lower(section)='newznab' AND lower(name)='newznab_data'").fetchone()
        chunks = row['value'].strip().strip('"').split('!!!')
        if index >= len(chunks) or hashlib.sha256(chunks[index].encode()).hexdigest() != revision:
            raise ValueError('Provider changed since this form opened. Refresh and review it again.')
        # Preserve positions of other entries so their open edit forms stay valid.
        chunks[index] = ''
        c.execute("UPDATE settings SET value=?,is_secret=1,updated_at=CURRENT_TIMESTAMP WHERE lower(section)='newznab' AND lower(name)='newznab_data'", ('!!!'.join(chunks),))


def test(identity):
    import ops
    provider = raw_provider(identity)
    started = time.perf_counter()
    try:
        result = indexer_client.capabilities(provider, force=True)
        # caps may be public; exercise an authenticated, non-download search too.
        mode = 'search' if 'search' in result['modes'] else 'tvsearch'
        root = indexer_client.request_xml(provider, {'t': mode, 'q': 'TVManagerConnectionTest', 'limit': 1})
        if indexer_client._tag(root) != 'rss':
            raise indexer_client.IndexerError('Indexer did not return a search feed for the connection test.')
        ops.provider_result(provider['name'], True, (time.perf_counter() - started) * 1000)
        return {'ok': True, 'message': 'Capabilities and authenticated search succeeded. No download was requested.', **result}
    except Exception as error:
        ops.provider_result(provider['name'], False, (time.perf_counter() - started) * 1000, error)
        raise ValueError(indexer_client.safe_error(error)) from None
