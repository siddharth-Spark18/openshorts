import base64
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from owner_workspace import ClipLibrary, install

import factory_tts
import jobs_db


def test_google_speech_enforces_global_limit_before_request(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    monkeypatch.setattr(factory_tts, 'MONTHLY_LIMIT', 10)
    monkeypatch.delenv('GOOGLE_TTS_CREDENTIALS_JSON', raising=False)
    jobs_db.init_db()
    creds = SimpleNamespace(token='token', refresh=lambda request: None)
    monkeypatch.setattr(factory_tts.google.auth, 'default', lambda **kwargs: (creds, 'project'))
    calls = []
    def post(url, **kwargs):
        calls.append(kwargs['json'])
        return httpx.Response(200, json={'audioContent': base64.b64encode(b'wave').decode()}, request=httpx.Request('POST', url))
    monkeypatch.setattr(factory_tts.httpx, 'post', post)
    factory_tts.synthesize('hello', tmp_path / 'one.wav', 'en-US-Neural2-F')
    assert (tmp_path / 'one.wav').read_bytes() == b'wave'
    assert calls[0]['voice']['name'] == 'en-US-Neural2-F'
    with pytest.raises(factory_tts.SpeechError, match='limit'):
        factory_tts.synthesize('another', tmp_path / 'two.wav', 'en-US-Neural2-D')
    assert len(calls) == 1


def test_google_speech_rejects_unconfigured_credentials_without_spending(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    monkeypatch.delenv('GOOGLE_TTS_CREDENTIALS_JSON', raising=False)
    jobs_db.init_db()
    def fail(**kwargs):
        raise RuntimeError('no credentials')
    monkeypatch.setattr(factory_tts.google.auth, 'default', fail)
    with pytest.raises(factory_tts.SpeechError, match='credentials'):
        factory_tts.synthesize('hello', tmp_path / 'no.wav', 'en-US-Neural2-F')
    with jobs_db._conn() as con:
        assert con.execute('SELECT COUNT(*) AS n FROM factory_tts_usage').fetchone()['n'] == 0


def test_project_voice_selection_is_private_and_persistent(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    jobs_db.init_db()
    app = FastAPI()
    install(app, 'password', ClipLibrary(tmp_path / 'library'))
    client = TestClient(app, follow_redirects=False)
    client.post('/owner/login', data={'password': 'password'})
    project = client.post('/api/factory/channels', json={'name': 'Office', 'content_type': 'workplace_skits'}).json()['id']
    settings = {'provider': 'google', 'voice_one': 'en-US-Neural2-C', 'voice_two': 'en-US-Neural2-J'}
    assert client.put(f'/api/factory/channels/{project}/voice', json={**settings, 'voice_one': 'bad'}).status_code == 400
    assert client.put(f'/api/factory/channels/{project}/voice', json=settings).status_code == 200
    jobs_db.init_db()
    assert client.get('/api/factory/channels').json()['channels'][0]['voice_settings'] == settings
