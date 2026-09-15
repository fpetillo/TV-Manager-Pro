import sqlite3
import pytest
import dbcore
import engine
import advanced
import ops
import provider_manager as manager
import indexer_client as client

CAPS = b'<caps><limits max="2"/><searching><search available="yes" supportedParams="q"/><tv-search available="yes" supportedParams="q,season,ep"/></searching><categories><category id="5000" name="TV"/></categories></caps>'


class Response:
    def __init__(self, data, status=200, headers=None):
        self.data, self.status_code, self.headers, self.closed = data, status, headers or {}, False
    def iter_content(self, size):
        yield self.data
    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def empty_cache():
    client._caps.clear()


def test_imported_disabled_flag_is_authoritative_and_schedule_flags_apply():
    rows = manager.parse('Disabled|https://disabled.test|key|5000|0|episode|0|1|1!!!Manual|https://manual.test|k|5000|1|episode|0|0|0', 'disabled manual')
    p = {x['name']: x for x in rows}
    assert not p['Disabled']['enabled'] and not manager.eligible(p['Disabled'])
    assert manager.eligible(p['Manual'])
    assert not manager.eligible(p['Manual'], 'recent') and not manager.eligible(p['Manual'], 'backlog')


@pytest.mark.parametrize('url,expected', [('https://a.test','https://a.test/api'),('https://a.test/index/api/','https://a.test/index/api'),('http://localhost:9117/api/v2.0/indexers/test/results/torznab/api','http://localhost:9117/api/v2.0/indexers/test/results/torznab/api')])
def test_endpoint_does_not_double_api(url, expected):
    assert client.endpoint(url) == expected


@pytest.mark.parametrize('url', ['http://news.newshosting.com:119','https://news.newshosting.com','nntp://news.test','https://user:secret@a.test','https://a.test/api?apikey=secret'])
def test_bad_endpoint_cannot_leak_credentials_or_treat_news_server_as_indexer(url):
    with pytest.raises(client.IndexerError) as error:
        client.endpoint(url)
    assert 'secret' not in str(error.value)


@pytest.mark.parametrize('response,code', [(Response(b'<error code="100" description="SECRET"/>'),100),(Response(b'<html>Login SECRET</html>'),None),(Response(b'',429,{'Retry-After':'180'}),429)])
def test_error_responses_are_not_empty_successful_searches(monkeypatch, response, code):
    monkeypatch.setattr(client.requests,'get',lambda *a,**k:response)
    with pytest.raises(client.IndexerError) as error:
        client.search({'url':'https://a.test','api_key':'SECRET'}, {'t':'tvsearch','q':'Show','season':1,'ep':2})
    assert 'SECRET' not in str(error.value) and error.value.code == code and response.closed
    if code == 429:
        assert error.value.retry_after == 180


def test_caps_fallback_and_pagination_preserve_results_and_seeders(monkeypatch):
    calls = []
    def get(url, **kw):
        assert kw['allow_redirects'] is False and kw['stream'] is True
        p = kw['params'];calls.append(dict(p))
        if p['t'] == 'caps':
            return Response(CAPS.replace(b'tv-search available="yes"', b'tv-search available="no"'))
        assert p['q'] == 'Show S01E02' and p['t'] == 'search' and 'season' not in p
        off = int(p['offset'])
        items = ''.join(f'<item><title>Show S01E02 {i}</title><guid>{i}</guid><enclosure url="https://a.test/get/{i}" length="200"/><attr name="seeders" value="4"/></item>' for i in range(off, min(off+2,3)))
        return Response(f'<rss><channel><response offset="{off}" total="3"/>{items}</channel></rss>'.encode())
    monkeypatch.setattr(client.requests,'get',get)
    rows=client.search({'url':'https://a.test','api_key':'secret'}, {'t':'tvsearch','q':'Show','season':1,'ep':2})
    assert len(rows)==3 and rows[0]['seeders']==4 and rows[0]['size']==200
    assert [x.get('offset') for x in calls]==[None,0,2]


def test_repeated_page_stops_and_unsupported_tv_function_falls_back(monkeypatch):
    calls=[]
    def get(url, **kw):
        p=kw['params'];calls.append(dict(p))
        if p['t']=='caps':return Response(CAPS)
        if p['t']=='tvsearch':return Response(b'<error code="203"/>')
        return Response(b'<rss><channel><item><guid>one</guid><link>https://a.test/1</link></item><item><guid>two</guid><link>https://a.test/2</link></item></channel></rss>')
    monkeypatch.setattr(client.requests,'get',get)
    rows=client.search({'url':'https://a.test'}, {'t':'tvsearch','q':'Show','season':1,'ep':2})
    assert len(rows)==2 and len(calls)==4


@pytest.fixture
def database(tmp_path, monkeypatch):
    database=tmp_path/'test.db'
    for module in (engine,advanced,ops):monkeypatch.setattr(module,'DB',database)
    with dbcore.connect(database) as c:
        c.executescript('''CREATE TABLE settings(section,name,value,is_secret,source,updated_at,UNIQUE(section,name));
        CREATE TABLE episodes(id);''')
        c.execute("INSERT INTO settings VALUES('Newznab','newznab_data',?,1,'import','')",('Fixture|https://a.test|SECRET|5000|1|season|1|0|1|extra-field',))
    advanced.init();ops.init()
    return database


def test_edit_preserves_secret_extended_fields_and_rejects_stale_form(database):
    row=engine.parse_newznab()[0]
    body=dict(row,api_key=manager.MASK,enabled=False,enable_daily=True)
    manager.save(row['id'],body)
    saved=engine.get_setting('Newznab','newznab_data')
    assert saved=='Fixture|https://a.test|SECRET|5000|0|season|1|1|1|extra-field'
    with pytest.raises(ValueError, match='changed'):
        manager.save(row['id'],body)
    assert all('SECRET' not in str(p) for p in manager.listing())
    new=engine.parse_newznab()[0]
    manager.remove(new['id'],new['revision'])
    assert engine.parse_newznab()==[]


def test_rate_limit_immediately_suspends_and_success_clears_health(database):
    ops.provider_result('Fixture',False,error=client.IndexerError('Rate limit',retry_after=600))
    assert not ops.provider_is_available('Fixture')
    ops.provider_result('Fixture',True)
    assert ops.provider_is_available('Fixture') and not ops.provider_health()[0]['last_error']


def test_connection_test_verifies_search_after_public_caps(database,monkeypatch):
    calls=[]
    def get(url, **kw):
        calls.append(kw['params']['t'])
        return Response(CAPS if calls[-1]=='caps' else b'<error code="100"/>')
    monkeypatch.setattr(client.requests,'get',get)
    with pytest.raises(ValueError,match='API key was rejected'):
        manager.test('imported-0')
    assert calls==['caps','search']


def test_historical_query_secrets_are_redacted():
    value=client.redact_error('GET /api?apikey=SECRET&token=OTHER q=test')
    assert 'SECRET' not in value and 'OTHER' not in value
