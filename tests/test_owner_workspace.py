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
