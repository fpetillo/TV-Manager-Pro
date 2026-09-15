"""Newznab/Torznab transport, capability discovery and bounded result paging."""
import hashlib
import re
import threading
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from xml.etree import ElementTree as ET

import requests

MAX_RESPONSE = 8 * 1024 * 1024
_caps = {}
_lock = threading.RLock()


class IndexerError(ValueError):
    def __init__(self, message, code=None, retry_after=None):
        super().__init__(message)
        self.code, self.retry_after = code, retry_after


def endpoint(value):
    try:
        url = urlsplit(str(value).strip())
        port = url.port
    except ValueError:
        raise IndexerError('Enter a valid indexer HTTP/HTTPS address.') from None
    if url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password:
        raise IndexerError('Use an HTTP/HTTPS indexer address and the separate API key field.')
    if port in {119, 563} or url.hostname.lower() in {'news.newshosting.com', 'unlimited.newshosting.com'}:
        raise IndexerError('This is a Usenet news server. Configure it in your downloader and use an indexer address here.')
    if url.query or url.fragment:
        raise IndexerError('Enter the indexer base URL or /api endpoint without query parameters; enter the API key separately.')
    path = url.path.rstrip('/')
    if not path.lower().endswith(('/api', '/api.php')):
        path += '/api'
    return urlunsplit((url.scheme, url.netloc, path, '', ''))


def safe_error(error):
    if isinstance(error, IndexerError):
        return str(error)
    if isinstance(error, requests.Timeout):
        return 'Indexer timed out. Check its availability and try again later.'
    if isinstance(error, requests.exceptions.SSLError):
        return 'Indexer TLS certificate could not be verified. Check its HTTPS address and certificate.'
    if isinstance(error, requests.ConnectionError):
        return 'Could not connect to the indexer. Check its address, DNS and network availability.'
    return 'Indexer request failed. Check its address, API key and service availability.'


def redact_error(text):
    # Also redact historical requests exceptions saved before safe_error existed.
    text = re.sub(r'(?i)(apikey|api_key|token|password|passkey|username)=([^&\s\)\]\"\']+)', r'\1=[redacted]', str(text or ''))
    return re.sub(r'(https?://)[^/@\s]+:[^/@\s]+@', r'\1[redacted]@', text)


def _tag(node):
    return node.tag.rsplit('}', 1)[-1]


def request_xml(provider, params, timeout=25):
    target = endpoint(provider['url'])
    query = dict(params, o='xml')
    if provider.get('api_key'):
        query['apikey'] = provider['api_key']
    started = time.monotonic()
    try:
        response = requests.get(target, params=query, timeout=(min(10, timeout), timeout),
                                headers={'User-Agent': 'TVManager/Indexer'}, allow_redirects=False, stream=True)
        try:
            status = response.status_code
            if status == 429:
                delay = response.headers.get('Retry-After', '')
                raise IndexerError('Indexer rate limit reached. Searches will wait before retrying.', code=429,
                                   retry_after=min(86400, max(60, int(delay))) if str(delay).isdigit() else 3600)
            if status in {401, 403}:
                raise IndexerError('Indexer rejected access. Check the API key, account access and IP restrictions.', code=status)
            if 300 <= status < 400:
                raise IndexerError('Indexer redirected the request. Save its current API endpoint address.')
            if status != 200:
                raise IndexerError(f'Indexer returned HTTP {status}. Check its service status and API address.', code=status)
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > MAX_RESPONSE or time.monotonic() - started > timeout:
                    raise IndexerError('Indexer response exceeded its size or time limit.')
        finally:
            response.close()
    except requests.RequestException as error:
        raise IndexerError(safe_error(error)) from None
    if b'<!DOCTYPE' in content.upper() or b'<!ENTITY' in content.upper():
        raise IndexerError('Indexer returned an unsupported document. Check the API address.')
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        raise IndexerError('Indexer did not return valid XML. Check the API address and account access.') from None
    error = next((n for n in root.iter() if _tag(n) == 'error'), None)
    if error is not None:
        try:
            code = int(error.get('code', '900'))
        except ValueError:
            code = 900
        messages = {100: 'API key was rejected.', 101: 'Account is suspended.',
                    102: 'Account does not have permission to use this API.',
                    200: 'A required search parameter is missing.', 201: 'A search parameter was rejected.',
                    202: 'Search function is not supported.', 203: 'Search function is unavailable.',
                    910: 'Indexer API is disabled.', 500: 'API request limit reached.'}
        raise IndexerError(f'Indexer error {code}: {messages.get(code, "The indexer could not complete this request.")}',
                           code=code, retry_after=3600 if code in {429, 500} else None)
    return root


def capabilities(provider, force=False):
    identity = hashlib.sha256((endpoint(provider['url']) + '\0' + (provider.get('api_key') or '')).encode()).hexdigest()
    with _lock:
        cached = _caps.get(identity)
        if not force and cached and time.monotonic() - cached[0] < 3600:
            return cached[1]
    root = request_xml(provider, {'t': 'caps'})
    if _tag(root) != 'caps':
        raise IndexerError('This endpoint did not return indexer capabilities. Check its API address.')
    modes, categories = {}, []
    maximum = 100
    for node in root.iter():
        tag = _tag(node)
        if tag in {'search', 'tv-search'}:
            if node.get('available', '').lower() in {'yes', '1', 'true'}:
                modes['tvsearch' if tag == 'tv-search' else 'search'] = [v.strip().lower() for v in node.get('supportedParams', '').split(',') if v.strip()]
        elif tag in {'category', 'subcat'} and str(node.get('id', '')).isdigit():
            categories.append({'id': node.get('id'), 'name': node.get('name', '')})
        elif tag == 'limits':
            try:
                maximum = max(1, min(100, int(node.get('max', '100'))))
            except ValueError:
                pass
    if not modes:
        raise IndexerError('Indexer does not advertise an available TV or text search.')
    result = {'modes': modes, 'categories': categories, 'limit': maximum}
    with _lock:
        if len(_caps) >= 256:
            _caps.clear()
        _caps[identity] = (time.monotonic(), result)
    return result


def text_query(params):
    query = params.get('q', '')
    if params.get('season') is not None:
        query += f" S{int(params['season']):02d}"
        if params.get('ep') is not None:
            query += f"E{int(params['ep']):02d}"
    return {'t': 'search', 'q': query.strip()}


def search(provider, params, timeout=25):
    caps = capabilities(provider)
    params = dict(params)
    mode = params['t']
    if mode == 'tvsearch' and (mode not in caps['modes'] or any(k not in caps['modes'][mode] for k in ('q', 'season', 'ep') if k in params)):
        params = text_query(params)
    if params['t'] not in caps['modes']:
        raise IndexerError('Indexer does not support the search required for this show numbering.')
    if provider.get('categories'):
        params['cat'] = provider['categories']
    params.update(extended='1', limit=caps['limit'])
    results, seen = [], set()
    for page in range(5):
        params['offset'] = page * caps['limit']
        try:
            root = request_xml(provider, params, timeout)
        except IndexerError as error:
            if page == 0 and params['t'] == 'tvsearch' and error.code in {202, 203} and 'search' in caps['modes']:
                params = dict(params, **text_query(params))
                params.pop('season', None)
                params.pop('ep', None)
                root = request_xml(provider, params, timeout)
            else:
                raise
        if _tag(root) != 'rss':
            raise IndexerError('Indexer did not return a search feed. Check the API endpoint.')
        items = [n for n in root.iter() if _tag(n) == 'item']
        new = 0
        for item in items:
            data = {_tag(n): n.text or '' for n in item}
            attrs = {n.get('name'): n.get('value') for n in item.iter() if _tag(n) == 'attr'}
            enclosure = next((n for n in item if _tag(n) == 'enclosure'), None)
            link = enclosure.get('url') if enclosure is not None else data.get('link')
            link = link or data.get('link') or ''
            guid = data.get('guid') or link
            if not link or not guid or guid in seen:
                continue
            seen.add(guid)
            def number(value):
                try:
                    return max(0, int(value or 0))
                except (ValueError, TypeError):
                    return 0
            results.append({'title': data.get('title', ''), 'url': link, 'guid': guid,
                            'size': number(enclosure.get('length') if enclosure is not None else attrs.get('size')),
                            'seeders': number(attrs.get('seeders')), 'publish_date': data.get('pubDate')})
            new += 1
        info = next((n for n in root.iter() if _tag(n) == 'response'), None)
        try:
            total = int(info.get('total')) if info is not None else None
        except (ValueError, TypeError):
            total = None
        if not new or len(items) < caps['limit'] or (total is not None and (page + 1) * caps['limit'] >= total):
            break
    return results
