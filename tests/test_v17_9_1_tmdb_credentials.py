import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

import tmdb_client
import metadata_service


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=''):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'{self.status_code} error')


class FakeRequests:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append({'url': url, 'headers': headers or {}, 'params': params or {}, 'timeout': timeout})
        return self.response


class TMDBCredentialTests(unittest.TestCase):
    def test_legacy_v3_api_key_is_supported(self):
        fake = FakeRequests(FakeResponse(payload={'ok': True}))
        with mock.patch.dict(os.environ, {'TMDB_API_KEY': 'legacy-key'}, clear=True):
            result = tmdb_client.get('/find/tt4577466', {'external_source': 'imdb_id'}, session=fake)
        self.assertEqual(result, {'ok': True})
        self.assertEqual(fake.calls[0]['params']['api_key'], 'legacy-key')
        self.assertNotIn('Authorization', fake.calls[0]['headers'])

    def test_bearer_token_is_supported(self):
        fake = FakeRequests(FakeResponse(payload={'ok': True}))
        with mock.patch.dict(os.environ, {'TMDB_BEARER_TOKEN': 'bearer-token'}, clear=True):
            tmdb_client.get('/tv/1', session=fake)
        self.assertEqual(fake.calls[0]['headers']['Authorization'], 'Bearer bearer-token')
        self.assertNotIn('api_key', fake.calls[0]['params'])

    def test_settings_table_tmdb_key_is_supported(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'tvmanager.db'
            con = sqlite3.connect(db)
            con.execute('CREATE TABLE settings(section TEXT,name TEXT,value TEXT)')
            con.execute('INSERT INTO settings VALUES(?,?,?)', ('General', 'tmdb_api_key', 'from-settings'))
            con.commit(); con.close()
            with mock.patch.dict(os.environ, {}, clear=True):
                cred = tmdb_client.credentials(db)
        self.assertEqual(cred['mode'], 'api_key')
        self.assertEqual(cred['value'], 'from-settings')

    def test_401_becomes_operator_friendly_error(self):
        fake = FakeRequests(FakeResponse(status_code=401, text='Invalid API key'))
        with mock.patch.dict(os.environ, {'TMDB_API_KEY': 'bad-key'}, clear=True):
            with self.assertRaises(tmdb_client.TMDBUnauthorizedError) as cm:
                tmdb_client.get('/find/tt4577466', {'external_source': 'imdb_id'}, session=fake)
        self.assertIn('HTTP 401 Unauthorized', str(cm.exception))
        self.assertIn('TMDB_API_KEY', str(cm.exception))

    def test_metadata_refresh_accepts_batch_size_keyword(self):
        old_db = metadata_service.DB
        try:
            with tempfile.TemporaryDirectory() as td:
                db = Path(td) / 'tvmanager.db'
                metadata_service.DB = db
                con = sqlite3.connect(db)
                con.execute('CREATE TABLE settings(section TEXT,name TEXT,value TEXT)')
                con.execute('CREATE TABLE shows(id INTEGER PRIMARY KEY, name TEXT, paused INTEGER DEFAULT 0, metadata_enabled INTEGER DEFAULT 1, tmdb_id INTEGER, imdb_id TEXT, tvdb_id INTEGER)')
                con.commit(); con.close()
                metadata_service.init()
                result = metadata_service.refresh_batch(batch_size=5)
            self.assertEqual(result['eligible_selected'], 0)
            self.assertEqual(result['batch_size'], 5)
        finally:
            metadata_service.DB = old_db


if __name__ == '__main__':
    unittest.main()
