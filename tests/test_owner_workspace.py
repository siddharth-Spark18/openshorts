from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from owner_workspace import ClipLibrary, install


def test_private_workspace_lifecycle(tmp_path):
    source = tmp_path / "job"
    source.mkdir()
    video = source / "generated.mp4"
    video.write_bytes(b"generated clip")
    job_id = str(uuid4())
    job = {"status": "completed", "output_dir": source, "result": {"clips": [
        {"title": "First clip", "video_url": f"/videos/{job_id}/{video.name}"}]}}
    library = ClipLibrary(tmp_path / "library")
    library.archive(job_id, job)
    app = FastAPI()
    install(app, "test password", library)
    client = TestClient(app, follow_redirects=False)
    url = f"/api/library/{job_id}/0"
    for route in (url, "/api/library", "/videos/file.mp4", "/owner/check"):
        assert client.get(route).status_code == 401
    assert client.delete(url).status_code == 401
    assert client.post("/owner/login", data={"password": "incorrect"}).status_code == 401
    login = client.post("/owner/login", data={"password": "test password"})
    assert login.status_code == 303 and "HttpOnly" in login.headers["set-cookie"]
    assert client.get("/owner/check").status_code == 204
    assert client.get("/api/library").json()[0]["title"] == "First clip"
    video.unlink()  # Temporary job expires.
    assert client.get(url).content == b"generated clip"
    assert client.delete(url).status_code == 204
    library.archive(job_id, job)
    assert client.get(url).status_code == 404
    assert ClipLibrary(library.root).clips() == []
    assert client.post("/owner/logout").status_code == 303
    assert client.get("/api/library").status_code == 401


def test_youtube_cookies_are_private_persistent_and_removable(tmp_path, monkeypatch):
    path = tmp_path / "youtube-cookies.txt"
    monkeypatch.setenv("YOUTUBE_COOKIES_PATH", str(path))
    app = FastAPI()
    install(app, "password", ClipLibrary(tmp_path / "library"))
    client = TestClient(app, follow_redirects=False)
    contents = b"# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tvalue\n"
    assert client.put("/api/youtube-cookies", files={"file": ("cookies.txt", contents)}).status_code == 401
    client.post("/owner/login", data={"password": "password"})
    assert client.put("/api/youtube-cookies", files={"file": ("bad.txt", b"bad")}).status_code == 400
    assert client.put("/api/youtube-cookies", files={"file": ("cookies.txt", contents)}).status_code == 200
    assert path.read_bytes() == contents
    assert path.stat().st_mode & 0o777 == 0o600
    assert client.get("/api/youtube-cookies").json() == {"configured": True}
    assert client.delete("/api/youtube-cookies").status_code == 204
    assert not path.exists()


def test_drive_authorization_requires_login_and_checks_state(tmp_path, monkeypatch):
    monkeypatch.setenv("DRIVE_CLIENT_ID", "123-test.apps.googleusercontent.com")
    monkeypatch.setenv("DRIVE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("DRIVE_PICKER_API_KEY", "test-picker")
    app = FastAPI()
    install(app, "password", ClipLibrary(tmp_path / "library"))
    client = TestClient(app, follow_redirects=False)
    assert client.get("/api/drive/connect").status_code == 401
    client.post("/owner/login", data={"password": "password"})
    response = client.get("/api/drive/connect")
    assert response.status_code == 307
    assert "code_challenge=" in response.headers["location"]
    assert client.get("/api/drive/callback?state=invalid&code=invalid").status_code == 400
    assert client.get("/api/drive/status").json()["connected"] is False


def test_owner_source_channels_persist_and_validate(tmp_path, monkeypatch):
    import jobs_db
    monkeypatch.setattr(jobs_db, "_DB_PATH", str(tmp_path / "jobs.db"))
    jobs_db.init_db()
    app = FastAPI()
    install(app, "password", ClipLibrary(tmp_path / "library"))
    client = TestClient(app, follow_redirects=False)
    assert client.get("/api/source-channels").status_code == 401
    client.post("/owner/login", data={"password": "password"})
    response = client.post("/api/source-channels", json={"url": "https://youtube.com/@IShowSpeed/videos"})
    assert response.status_code == 201
    assert response.json()["url"] == "https://www.youtube.com/@IShowSpeed"
    assert client.post("/api/source-channels", json={"url": "https://www.youtube.com/@IShowSpeed"}).status_code == 409
    assert client.post("/api/source-channels", json={"url": "https://example.com/@channel"}).status_code == 400
    channel_id = response.json()["id"]
    assert len(client.get("/api/source-channels").json()["channels"]) == 1
    assert client.delete(f"/api/source-channels/{channel_id}").status_code == 204
    assert client.get("/api/source-channels").json()["channels"] == []


def test_remote_clip_can_be_downloaded_after_local_copy_is_gone(tmp_path, monkeypatch):
    import json
    import httpx
    import owner_workspace
    import drive_connection

    library = ClipLibrary(tmp_path / "library")
    job_id = str(uuid4())
    directory = library.root / job_id
    directory.mkdir()
    (directory / "index.json").write_text(json.dumps([{"index": 0, "title": "Saved", "filename": "clip.mp4"}]))
    (directory / ".drive-receipts.json").write_text(json.dumps({f"{job_id}-0": {"id": "file_id"}}))
    (library.root / ".drive-connection.json").write_text(json.dumps({"refresh_token": "private"}))

    async def token(_):
        return "access-token"
    monkeypatch.setattr(drive_connection, "refresh_access_token", token)
    client_type = httpx.AsyncClient

    def client_factory(**kwargs):
        def handler(request):
            assert request.headers["authorization"] == "Bearer access-token"
            return httpx.Response(200, headers={"Content-Length": "4"}, content=b"clip")
        return client_type(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(owner_workspace.httpx, "AsyncClient", client_factory)
    app = FastAPI()
    install(app, "password", library)
    client = TestClient(app, follow_redirects=False)
    client.post("/owner/login", data={"password": "password"})
    assert len(client.get("/api/library").json()) == 1
    assert client.get(f"/api/library/{job_id}/0").content == b"clip"
    assert client.delete(f"/api/library/{job_id}/0").status_code == 204
    assert client.get("/api/library").json() == []


def test_discovered_videos_prioritize_topic_and_include_view_rate(tmp_path, monkeypatch):
    import jobs_db
    monkeypatch.setattr(jobs_db, "_DB_PATH", str(tmp_path / "jobs.db"))
    jobs_db.init_db()
    jobs_db.save_settings({"source_topics": "GTA 6"})
    with jobs_db._conn() as con:
        con.execute("INSERT INTO source_channels VALUES (?, ?, ?)", ("source", "https://www.youtube.com/@example", "2026-01-01"))
        con.execute("INSERT INTO source_videos VALUES (?, ?, ?, ?, ?)", ("abcdefghijk", "source", "Other video", "2026-11-25T00:00:00Z", "2026-11-27"))
        con.execute("INSERT INTO source_videos VALUES (?, ?, ?, ?, ?)", ("12345678901", "source", "GTA VI updates", "2026-11-25T00:00:00Z", "2026-11-27"))
        con.execute("INSERT INTO source_video_stats VALUES (?, ?, ?, ?)", ("12345678901", 1000, 10, "2026-11-27"))
    app = FastAPI()
    install(app, "password", ClipLibrary(tmp_path / "library"))
    client = TestClient(app, follow_redirects=False)
    client.post("/owner/login", data={"password": "password"})
    result = client.get("/api/source-videos").json()
    assert result["videos"][0]["title"] == "GTA VI updates"
    assert result["videos"][0]["topic_match"] is True
    assert result["videos"][0]["views_per_day"] is not None


def test_source_automation_can_be_paused_by_owner(tmp_path, monkeypatch):
    import jobs_db
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    jobs_db.init_db()
    app = FastAPI()
    install(app, 'password', ClipLibrary(tmp_path / 'library'))
    client = TestClient(app, follow_redirects=False)
    assert client.put('/api/source-automation', json={'enabled': False}).status_code == 401
    client.post('/owner/login', data={'password': 'password'})
    assert client.get('/api/source-automation').json() == {'enabled': True}
    assert client.put('/api/source-automation', json={'enabled': False}).json() == {'enabled': False}
    assert client.get('/api/source-automation').json() == {'enabled': False}


def test_factory_channels_and_idea_review_persist_privately(tmp_path, monkeypatch):
    import jobs_db
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    jobs_db.init_db()
    app = FastAPI()
    install(app, 'password', ClipLibrary(tmp_path / 'library'))
    client = TestClient(app, follow_redirects=False)
    assert client.get('/api/factory/channels').status_code == 401
    client.post('/owner/login', data={'password': 'password'})
    assert client.post('/api/factory/channels', json={'name': '  ', 'content_type': 'workplace_skits'}).status_code == 400
    channel = client.post('/api/factory/channels', json={'name': 'Office stories', 'content_type': 'workplace_skits'}).json()
    idea = client.post(f"/api/factory/channels/{channel['id']}/ideas", json={'idea': 'A meeting that could have been an email'}).json()
    assert idea['status'] == 'needs_review'
    assert client.patch(f"/api/factory/ideas/{idea['id']}", json={'status': 'approved'}).status_code == 200
    assert client.patch(f"/api/factory/ideas/{idea['id']}", json={'status': 'published'}).status_code == 400
    rows = client.get('/api/factory/channels').json()['channels']
    assert rows[0]['ideas'][0]['status'] == 'approved'
    jobs_db.init_db()
    assert client.get('/api/factory/channels').json()['channels'][0]['ideas'][0]['idea'].startswith('A meeting')


def test_workplace_script_generation_edit_and_review(tmp_path, monkeypatch):
    import jobs_db
    import factory_story
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    monkeypatch.setenv('GEMINI_API_KEY', 'example')
    monkeypatch.setattr(factory_story, 'generate_script', lambda idea, key: f'Title: A meeting\nBoss: {idea}')
    jobs_db.init_db()
    app = FastAPI()
    install(app, 'password', ClipLibrary(tmp_path / 'library'))
    client = TestClient(app, follow_redirects=False)
    assert client.post(f'/api/factory/ideas/{uuid4()}/script').status_code == 401
    client.post('/owner/login', data={'password': 'password'})
    channel = client.post('/api/factory/channels', json={'name': 'Office', 'content_type': 'workplace_skits'}).json()
    idea = client.post(f"/api/factory/channels/{channel['id']}/ideas", json={'idea': 'No meetings'}).json()
    url = f"/api/factory/ideas/{idea['id']}"
    assert client.post(url + '/script').status_code == 400
    client.patch(url, json={'status': 'approved'})
    draft = client.post(url + '/script').json()
    assert draft['status'] == 'needs_review' and draft['revision'] == 1
    approved = client.patch(url + '/script/review', json={'status': 'approved', 'revision': 1}).json()
    assert approved['revision'] == 2
    assert client.put(url + '/script', json={'script': 'Stale edit', 'revision': 1}).status_code == 409
    edited = client.put(url + '/script', json={'script': 'Edited script', 'revision': 2}).json()
    assert edited['status'] == 'needs_review' and edited['revision'] == 3
    client.patch(url, json={'status': 'rejected'})
    assert client.patch(url + '/script/review', json={'status': 'approved', 'revision': 3}).status_code == 409
    item = client.get('/api/factory/channels').json()['channels'][0]['ideas'][0]
    assert item['script'] == 'Edited script' and item['script_status'] == 'needs_review'


def test_project_settings_are_private_persistent_and_used_for_scripts(tmp_path, monkeypatch):
    import jobs_db
    import factory_story
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    monkeypatch.setenv('GEMINI_API_KEY', 'example')
    monkeypatch.setattr(factory_story, 'generate_script', lambda idea, key: 'Boss: ' + idea)
    jobs_db.init_db()
    app = FastAPI()
    install(app, 'password', ClipLibrary(tmp_path / 'library'))
    client = TestClient(app, follow_redirects=False)
    settings = {'style': 'Dry humor', 'daily_target': 3, 'publishing_mode': 'automatic'}
    assert client.put(f'/api/factory/channels/{uuid4()}/settings', json=settings).status_code == 401
    client.post('/owner/login', data={'password': 'password'})
    first = client.post('/api/factory/channels', json={'name': 'Office', 'content_type': 'workplace_skits'}).json()
    second = client.post('/api/factory/channels', json={'name': 'Other', 'content_type': 'workplace_skits'}).json()
    endpoint = f"/api/factory/channels/{first['id']}/settings"
    assert client.put(endpoint, json={**settings, 'daily_target': 0}).status_code == 400
    assert client.put(endpoint, json={**settings, 'publishing_mode': 'invalid'}).status_code == 400
    assert client.put(f'/api/factory/channels/{uuid4()}/settings', json=settings).status_code == 404
    assert client.put(endpoint, json=settings).json() == settings
    jobs_db.init_db()
    projects = {p['id']: p for p in client.get('/api/factory/channels').json()['channels']}
    assert projects[first['id']]['settings'] == settings
    assert projects[second['id']]['settings']['publishing_mode'] == 'manual'
    idea = client.post(f"/api/factory/channels/{first['id']}/ideas", json={'idea': 'A meeting'}).json()
    client.patch(f"/api/factory/ideas/{idea['id']}", json={'status': 'approved'})
    assert 'Dry humor' in client.post(f"/api/factory/ideas/{idea['id']}/script").json()['script']


def test_skit_render_requires_approval_and_invalidates_after_edit(tmp_path, monkeypatch):
    import jobs_db
    import factory_story
    import factory_render
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    monkeypatch.setenv('GEMINI_API_KEY', 'example')
    monkeypatch.setattr(factory_story, 'generate_script', lambda idea, key: 'Boss: Hello there.')
    def fake_render(script, output):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b'video')
    monkeypatch.setattr(factory_render, 'render', fake_render)
    jobs_db.init_db()
    app = FastAPI()
    install(app, 'password', ClipLibrary(tmp_path / 'library'))
    with TestClient(app, follow_redirects=False) as client:
        client.post('/owner/login', data={'password': 'password'})
        channel = client.post('/api/factory/channels', json={'name': 'Office', 'content_type': 'workplace_skits'}).json()
        idea = client.post(f"/api/factory/channels/{channel['id']}/ideas", json={'idea': 'Meeting'}).json()
        url = f"/api/factory/ideas/{idea['id']}"
        client.patch(url, json={'status': 'approved'})
        client.post(url + '/script')
        assert client.post(url + '/render').status_code == 400
        client.patch(url + '/script/review', json={'status': 'approved', 'revision': 1})
        assert client.post(url + '/render').status_code == 202
        import time
        for _ in range(100):
            if client.get(url + '/video').status_code == 200:
                break
            time.sleep(0.01)
        assert client.get(url + '/video').content == b'video'
        assert any(item['title'] == 'Workplace skit' for item in client.get('/api/library').json())
        assert client.get('/api/factory/channels').json()['channels'][0]['ideas'][0]['video_ready'] == 1
        assert client.get('/api/factory/channels').json()['channels'][0]['ideas'][0]['queue_status'] == 'needs_review'
        assert client.put(url + '/video/review', json={'status': 'approved', 'revision': 1}).status_code == 409
        assert client.put(url + '/video/review', json={'status': 'approved', 'revision': 2}).status_code == 200
        assert client.get('/api/factory/channels').json()['channels'][0]['ideas'][0]['queue_status'] == 'approved'
        client.put(url + '/script', json={'script': 'Boss: Goodbye.', 'revision': 2})
        assert client.get(url + '/video').status_code == 404
        assert client.get('/api/factory/channels').json()['channels'][0]['ideas'][0]['queue_status'] is None


def test_generate_ideas_saves_batch_for_review(tmp_path, monkeypatch):
    import jobs_db
    import factory_story
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    monkeypatch.setenv('GEMINI_API_KEY', 'example')
    seen = []
    def generate(style, count, key):
        seen.append((style, count, key))
        return ['First funny meeting', 'Second funny meeting', 'Third funny meeting']
    monkeypatch.setattr(factory_story, 'generate_ideas', generate)
    jobs_db.init_db()
    app = FastAPI()
    install(app, 'password', ClipLibrary(tmp_path / 'library'))
    client = TestClient(app, follow_redirects=False)
    client.post('/owner/login', data={'password': 'password'})
    project = client.post('/api/factory/channels', json={'name': 'Office', 'content_type': 'workplace_skits'}).json()
    base = f"/api/factory/channels/{project['id']}"
    client.put(base + '/settings', json={'style': 'Dry humor', 'daily_target': 3, 'publishing_mode': 'manual'})
    assert client.post(base + '/ideas/generate', json={'count': 6}).status_code == 400
    response = client.post(base + '/ideas/generate', json={'count': 3})
    assert response.status_code == 201
    assert seen == [('Dry humor', 3, 'example')]
    jobs_db.init_db()
    ideas = client.get('/api/factory/channels').json()['channels'][0]['ideas']
    assert len(ideas) == 3 and all(idea['status'] == 'needs_review' for idea in ideas)


def test_skit_render_runs_in_background_and_rejects_parallel_work(tmp_path, monkeypatch):
    import time
    import threading
    import jobs_db
    import factory_story
    import factory_render
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    monkeypatch.setenv('GEMINI_API_KEY', 'example')
    monkeypatch.setattr(factory_story, 'generate_script', lambda idea, key: 'Boss: Hello.')
    started, finish = threading.Event(), threading.Event()
    def delayed(script, output):
        started.set()
        assert finish.wait(3)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b'video')
    monkeypatch.setattr(factory_render, 'render', delayed)
    jobs_db.init_db()
    app = FastAPI()
    install(app, 'password', ClipLibrary(tmp_path / 'library'))
    with TestClient(app, follow_redirects=False) as client:
        client.post('/owner/login', data={'password': 'password'})
        channel = client.post('/api/factory/channels', json={'name': 'Office', 'content_type': 'workplace_skits'}).json()
        idea = client.post(f"/api/factory/channels/{channel['id']}/ideas", json={'idea': 'Meeting'}).json()
        url = f"/api/factory/ideas/{idea['id']}"
        client.patch(url, json={'status': 'approved'})
        client.post(url + '/script')
        client.patch(url + '/script/review', json={'status': 'approved', 'revision': 1})
        try:
            assert client.post(url + '/render').status_code == 202
            assert started.wait(1)
            assert client.post(url + '/render').status_code == 409
            item = client.get('/api/factory/channels').json()['channels'][0]['ideas'][0]
            assert item['render_status'] == 'processing'
            client.put(url + '/script', json={'script': 'Boss: Changed.', 'revision': 2})
        finally:
            finish.set()
        for _ in range(100):
            item = client.get('/api/factory/channels').json()['channels'][0]['ideas'][0]
            if item['render_status'] != 'processing':
                break
            time.sleep(.01)
        assert item['render_status'] == 'failed'
        assert client.get(url + '/video').status_code == 404
