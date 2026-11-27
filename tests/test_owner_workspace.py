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
