from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

import factory_youtube
import jobs_db
from owner_workspace import ClipLibrary, install


def test_youtube_oauth_is_project_scoped_and_keeps_tokens_private(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    monkeypatch.setenv('YOUTUBE_CLIENT_ID', 'client-id')
    monkeypatch.setenv('YOUTUBE_CLIENT_SECRET', 'client-secret')
    jobs_db.init_db()
    library = ClipLibrary(tmp_path / 'library')
    app = FastAPI()
    install(app, 'password', library)
    client_type = httpx.AsyncClient
    def fake_http(**kwargs):
        def handle(request):
            if str(request.url) == factory_youtube.TOKEN_URL:
                assert b'code_verifier=' in request.content
                return httpx.Response(200, json={'access_token': 'access', 'refresh_token': 'secret-refresh'})
            assert request.headers['authorization'] == 'Bearer access'
            return httpx.Response(200, json={'items': [{'id': 'youtube-id', 'snippet': {'title': 'My channel'}}]})
        return client_type(transport=httpx.MockTransport(handle), **kwargs)
    monkeypatch.setattr(factory_youtube.httpx, 'AsyncClient', fake_http)
    client = TestClient(app, follow_redirects=False)
    assert client.get(f'/api/factory/channels/{uuid4()}/youtube/connect').status_code == 401
    client.post('/owner/login', data={'password': 'password'})
    first = client.post('/api/factory/channels', json={'name': 'One', 'content_type': 'workplace_skits'}).json()['id']
    second = client.post('/api/factory/channels', json={'name': 'Two', 'content_type': 'workplace_skits'}).json()['id']
    auth = client.get(f'/api/factory/channels/{first}/youtube/connect')
    query = parse_qs(urlparse(auth.headers['location']).query)
    assert query['code_challenge_method'] == ['S256']
    assert 'youtube.upload' in query['scope'][0]
    state = query['state'][0]
    assert client.get('/api/factory/youtube/callback', params={'state': state, 'code': 'example'}).status_code == 303
    assert client.get('/api/factory/youtube/callback', params={'state': state, 'code': 'example'}).status_code == 400
    rows = {p['id']: p for p in client.get('/api/factory/channels').json()['channels']}
    assert rows[first]['connections']['youtube']['channel_title'] == 'My channel'
    assert rows[second]['connections']['youtube']['connected'] is False
    assert 'secret-refresh' not in str(rows)
    token_path = library.root / '.youtube-connections' / f'{first}.json'
    assert token_path.stat().st_mode & 0o077 == 0
    assert client.delete(f'/api/factory/channels/{first}/youtube/connection').json() == {'connected': False}
    assert not token_path.exists()


def test_publication_requires_approval_and_prevents_duplicate_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    monkeypatch.setenv('YOUTUBE_CLIENT_ID', 'client-id')
    monkeypatch.setenv('YOUTUBE_CLIENT_SECRET', 'client-secret')
    jobs_db.init_db()
    library = ClipLibrary(tmp_path / 'library')
    app = FastAPI()
    install(app, 'password', library)
    client = TestClient(app, follow_redirects=False)
    client.post('/owner/login', data={'password': 'password'})
    project = client.post('/api/factory/channels', json={'name': 'Office', 'content_type': 'workplace_skits'}).json()['id']
    idea = client.post(f'/api/factory/channels/{project}/ideas', json={'idea': 'The endless meeting'}).json()['id']
    endpoint = f'/api/factory/ideas/{idea}/youtube/publish'
    assert client.post(endpoint).status_code == 400
    with jobs_db._conn() as con:
        con.execute("UPDATE factory_ideas SET status='approved' WHERE id=?", (idea,))
        con.execute("INSERT INTO factory_scripts VALUES (?, 'Boss: Hello.', 'approved', 2, 'now')", (idea,))
        con.execute("INSERT INTO factory_renders VALUES (?,2,'now')", (idea,))
        con.execute("INSERT INTO factory_review_queue VALUES (?,2,'approved','now')", (idea,))
    video = library.root / 'factory' / idea / '2.mp4'
    video.parent.mkdir(parents=True)
    video.write_bytes(b'video bytes')
    factory_youtube.write_connection(library.root, project, {'refresh_token': 'private', 'channel_id': 'channel'})
    client_type = httpx.AsyncClient
    seen = []
    def fake_http(**kwargs):
        async def handle(request):
            seen.append(request.url.path)
            if str(request.url) == factory_youtube.TOKEN_URL:
                return httpx.Response(200, json={'access_token': 'access'})
            if request.method == 'POST':
                return httpx.Response(200, headers={'location': 'https://www.googleapis.com/upload/session'})
            assert await request.aread() == b'video bytes'
            return httpx.Response(201, json={'id': 'video123'})
        return client_type(transport=httpx.MockTransport(handle), **kwargs)
    monkeypatch.setattr(factory_youtube.httpx, 'AsyncClient', fake_http)
    result = client.post(endpoint)
    assert result.status_code == 200 and result.json()['video_id'] == 'video123'
    assert client.post(endpoint).status_code == 409
    assert seen.count('/upload/session') == 1
    state = client.get('/api/factory/channels').json()['channels'][0]['ideas'][0]
    assert state['youtube_publication_status'] == 'published'


def test_upload_location_must_be_google_https(tmp_path, monkeypatch):
    # Invalid upload destinations must never receive the video.
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    monkeypatch.setenv('YOUTUBE_CLIENT_ID', 'client')
    monkeypatch.setenv('YOUTUBE_CLIENT_SECRET', 'secret')
    jobs_db.init_db()
    library = ClipLibrary(tmp_path / 'library')
    app = FastAPI()
    install(app, 'password', library)
    client = TestClient(app, follow_redirects=False)
    client.post('/owner/login', data={'password': 'password'})
    project = client.post('/api/factory/channels', json={'name': 'Office', 'content_type': 'workplace_skits'}).json()['id']
    idea = client.post(f'/api/factory/channels/{project}/ideas', json={'idea': 'The endless meeting'}).json()['id']
    with jobs_db._conn() as con:
        con.execute("UPDATE factory_ideas SET status='approved' WHERE id=?", (idea,))
        con.execute("INSERT INTO factory_scripts VALUES (?, 'Boss: Hello.', 'approved', 2, 'now')", (idea,))
        con.execute("INSERT INTO factory_renders VALUES (?,2,'now')", (idea,))
        con.execute("INSERT INTO factory_review_queue VALUES (?,2,'approved','now')", (idea,))
    video = library.root / 'factory' / idea / '2.mp4'
    video.parent.mkdir(parents=True)
    video.write_bytes(b'video')
    factory_youtube.write_connection(library.root, project, {'refresh_token': 'private', 'channel_id': 'channel'})
    client_type = httpx.AsyncClient
    def fake_http(**kwargs):
        def handle(request):
            if str(request.url) == factory_youtube.TOKEN_URL:
                return httpx.Response(200, json={'access_token': 'access'})
            return httpx.Response(200, headers={'location': 'https://attacker.example/upload'})
        return client_type(transport=httpx.MockTransport(handle), **kwargs)
    monkeypatch.setattr(factory_youtube.httpx, 'AsyncClient', fake_http)
    assert client.post(f'/api/factory/ideas/{idea}/youtube/publish').status_code == 502
    with jobs_db._conn() as con:
        assert con.execute('SELECT status FROM factory_publications').fetchone()['status'] == 'failed'
