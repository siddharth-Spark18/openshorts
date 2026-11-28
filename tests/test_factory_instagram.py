import time
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

import factory_instagram
import jobs_db
from owner_workspace import ClipLibrary, install


def test_instagram_connection_is_scoped_and_tokens_are_private(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    monkeypatch.setenv('INSTAGRAM_APP_ID', '123')
    monkeypatch.setenv('INSTAGRAM_APP_SECRET', 'secret')
    jobs_db.init_db()
    library = ClipLibrary(tmp_path / 'library')
    app = FastAPI()
    install(app, 'password', library)
    client_type = httpx.AsyncClient
    def fake_http(**kwargs):
        def handle(request):
            if request.url.host == 'api.instagram.com':
                return httpx.Response(200, json={'access_token': 'short', 'user_id': '100'})
            if request.url.path == '/access_token':
                return httpx.Response(200, json={'access_token': 'private-token', 'expires_in': 5184000})
            assert request.headers['authorization'] == 'Bearer private-token'
            return httpx.Response(200, json={'user_id': '100', 'username': 'office', 'account_type': 'BUSINESS'})
        return client_type(transport=httpx.MockTransport(handle), **kwargs)
    monkeypatch.setattr(factory_instagram.httpx, 'AsyncClient', fake_http)
    client = TestClient(app, follow_redirects=False)
    client.post('/owner/login', data={'password': 'password'})
    project = client.post('/api/factory/channels', json={'name': 'Office', 'content_type': 'workplace_skits'}).json()['id']
    auth = client.get(f'/api/factory/channels/{project}/instagram/connect')
    state = parse_qs(urlparse(auth.headers['location']).query)['state'][0]
    assert client.get('/api/factory/instagram/callback', params={'state': state, 'code': 'abc'}).status_code == 303
    assert client.get('/api/factory/instagram/callback', params={'state': state, 'code': 'abc'}).status_code == 400
    result = client.get('/api/factory/channels').json()
    assert result['channels'][0]['connections']['instagram']['username'] == 'office'
    assert 'private-token' not in str(result)
    assert (library.root / '.instagram-connections' / f'{project}.json').stat().st_mode & 0o077 == 0


def test_instagram_publish_uses_expiring_media_grant_and_prevents_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    jobs_db.init_db()
    library = ClipLibrary(tmp_path / 'library')
    app = FastAPI()
    install(app, 'password', library)
    client = TestClient(app, follow_redirects=False)
    client.post('/owner/login', data={'password': 'password'})
    project = client.post('/api/factory/channels', json={'name': 'Office', 'content_type': 'workplace_skits'}).json()['id']
    idea = client.post(f'/api/factory/channels/{project}/ideas', json={'idea': 'A funny meeting'}).json()['id']
    with jobs_db._conn() as con:
        con.execute("UPDATE factory_ideas SET status='approved' WHERE id=?", (idea,))
        con.execute("INSERT INTO factory_scripts VALUES (?, 'Boss: Hello.', 'approved', 2, 'now')", (idea,))
        con.execute("INSERT INTO factory_renders VALUES (?,2,'now')", (idea,))
        con.execute("INSERT INTO factory_review_queue VALUES (?,2,'approved','now')", (idea,))
    video = library.root / 'factory' / idea / '2.mp4'
    video.parent.mkdir(parents=True)
    video.write_bytes(b'video')
    factory_instagram.write_connection(library.root, project, {'access_token': 'private', 'user_id': '100',
                                      'issued_at': time.time(), 'expires_at': time.time() + 30 * 86400})
    client_type, media_urls = httpx.AsyncClient, []
    def fake_http(**kwargs):
        def handle(request):
            if request.url.path.endswith('/media'):
                import json
                media_urls.append(json.loads(request.content)['video_url'])
                with jobs_db._conn() as con:
                    assert con.execute('SELECT COUNT(*) AS n FROM factory_media_grants').fetchone()['n'] == 1
                return httpx.Response(200, json={'id': '101'})
            if request.method == 'GET':
                return httpx.Response(200, json={'status_code': 'FINISHED'})
            return httpx.Response(200, json={'id': '102'})
        return client_type(transport=httpx.MockTransport(handle), **kwargs)
    monkeypatch.setattr(factory_instagram.httpx, 'AsyncClient', fake_http)
    endpoint = f'/api/factory/ideas/{idea}/instagram/publish'
    assert client.post(endpoint).json()['media_id'] == '102'
    assert client.post(endpoint).status_code == 409
    assert client.get(urlparse(media_urls[0]).path).status_code == 404
    with jobs_db._conn() as con:
        assert con.execute('SELECT COUNT(*) AS n FROM factory_media_grants').fetchone()['n'] == 0
