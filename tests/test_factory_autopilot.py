import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

import factory_autopilot
import factory_render
import factory_story
import jobs_db
from owner_workspace import ClipLibrary, install


def test_autopilot_generates_renders_and_queues_one_video(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    monkeypatch.setenv('GEMINI_API_KEY', 'key')
    monkeypatch.setattr(factory_story, 'generate_ideas', lambda style, count, key: ['A meeting that refuses to end'])
    monkeypatch.setattr(factory_story, 'generate_script', lambda idea, key: 'Boss: This meeting is over.\nWorker: Finally.')
    def render(script, output):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b'video')
    monkeypatch.setattr(factory_render, 'render', render)
    jobs_db.init_db()
    app = FastAPI()
    install(app, 'password', ClipLibrary(tmp_path / 'library'))
    with TestClient(app, follow_redirects=False) as client:
        client.post('/owner/login', data={'password': 'password'})
        project = client.post('/api/factory/channels', json={'name': 'Office', 'content_type': 'workplace_skits'}).json()['id']
        client.put(f'/api/factory/channels/{project}/settings', json={'style': 'Dry humor', 'daily_target': 1, 'publishing_mode': 'automatic'})
        assert client.portal.call(factory_autopilot.produce_next, app)
        for _ in range(100):
            channel = client.get('/api/factory/channels').json()['channels'][0]
            if channel['auto_production']['status'] == 'idle':
                break
            time.sleep(.02)
        idea = channel['ideas'][0]
        assert idea['queue_status'] == 'approved'
        assert idea['schedule_status'] == 'pending'
        assert idea['instagram_schedule_status'] == 'pending'
        assert not client.portal.call(factory_autopilot.produce_next, app)
        assert len(client.get('/api/factory/channels').json()['channels'][0]['ideas']) == 1


def test_autopilot_does_not_generate_for_manual_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    monkeypatch.setenv('GEMINI_API_KEY', 'key')
    jobs_db.init_db()
    app = FastAPI()
    install(app, 'password', ClipLibrary(tmp_path / 'library'))
    with TestClient(app, follow_redirects=False) as client:
        client.post('/owner/login', data={'password': 'password'})
        client.post('/api/factory/channels', json={'name': 'Office', 'content_type': 'workplace_skits'})
        assert not client.portal.call(factory_autopilot.produce_next, app)
