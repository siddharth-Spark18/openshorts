import hashlib
import json
from pathlib import Path

import httpx

from drive_archive import DriveArchive


def test_upload_is_verified_and_not_duplicated_after_restart(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    video = job / "0.mp4"
    video.write_bytes(b"clip bytes")
    (job / "index.json").write_text(json.dumps([{"index": 0, "filename": "clip.mp4"}]))
    checksum = hashlib.md5(video.read_bytes()).hexdigest()
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path == "/drive/v3/files":
            return httpx.Response(200, json={"files": []})
        if request.method == "POST":
            return httpx.Response(200, headers={"location": "https://upload.test/session"})
        if request.method == "PUT":
            return httpx.Response(200, json={"id": "file-id"})
        return httpx.Response(200, json={"size": str(video.stat().st_size), "md5Checksum": checksum})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        archive = DriveArchive(tmp_path)
        archive._sync_job(client, {}, "folder_id", job / "index.json")
        count = len(calls)
        archive._sync_job(client, {}, "folder_id", job / "index.json")
    assert len(calls) == count
    assert json.loads((job / ".drive-receipts.json").read_text())["job-0"]["id"] == "file-id"


def test_failed_verification_keeps_the_local_clip(tmp_path):
    import pytest
    from drive_archive import DriveArchiveError

    job = tmp_path / "job"
    job.mkdir()
    (job / "0.mp4").write_bytes(b"original")
    (job / "index.json").write_text(json.dumps([{"index": 0, "filename": "clip.mp4"}]))

    def handler(request):
        if request.method == "GET" and request.url.path == "/drive/v3/files":
            return httpx.Response(200, json={"files": []})
        if request.method == "POST":
            return httpx.Response(200, headers={"location": "https://upload.test/session"})
        if request.method == "PUT":
            return httpx.Response(200, json={"id": "file-id"})
        return httpx.Response(200, json={"size": "1", "md5Checksum": "incorrect"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DriveArchiveError):
            DriveArchive(tmp_path)._sync_job(client, {}, "folder_id", job / "index.json")
    assert (job / "0.mp4").read_bytes() == b"original"
    assert not (job / ".drive-receipts.json").exists()


def test_matching_uploaded_file_is_reused_after_lost_response(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    data = b"already uploaded"
    (job / "0.mp4").write_bytes(data)
    (job / "index.json").write_text(json.dumps([{"index": 0, "filename": "clip.mp4"}]))
    checksum = hashlib.md5(data).hexdigest()

    def handler(request):
        assert request.method == "GET"
        if request.url.path == "/drive/v3/files":
            return httpx.Response(200, json={"files": [{"id": "existing", "size": str(len(data)),
                                                       "md5Checksum": checksum}]})
        return httpx.Response(200, json={"size": str(len(data)), "md5Checksum": checksum})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        DriveArchive(tmp_path)._sync_job(client, {}, "folder_id", job / "index.json")
    assert json.loads((job / ".drive-receipts.json").read_text())["job-0"]["id"] == "existing"
