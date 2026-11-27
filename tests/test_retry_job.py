import asyncio
import json
from uuid import uuid4

import httpx
import pytest

app_module = pytest.importorskip("app")


@pytest.fixture
def setup_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(app_module, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(app_module.jobs_db, "_DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.setattr(app_module, "owner_library", object())
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(app_module, "job_queue", asyncio.PriorityQueue())
    monkeypatch.setattr(app_module, "jobs", {})
    monkeypatch.setattr(app_module, "_running_jobs", set())
    (tmp_path / "output").mkdir()
    (tmp_path / "uploads").mkdir()
    app_module.jobs_db.init_db()
    job_id = str(uuid4())
    app_module.jobs_db.record_job_created(job_id, "https://www.youtube.com/watch?v=example")
    app_module.jobs_db.record_job_finished(job_id, "failed")
    output = tmp_path / "output" / job_id
    output.mkdir()
    (output / "source.mp4").write_bytes(b"source")
    (output / ".transcript_checkpoint.json").write_text("checkpoint")
    return job_id, output


def _post(job_id):
    async def call():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(f"/api/jobs/{job_id}/retry")
    return asyncio.run(call())


def test_retry_reuses_source_and_checkpoint_and_prevents_duplicate(setup_retry):
    job_id, output = setup_retry
    result = _post(job_id)
    assert result.status_code == 200
    job = app_module.jobs[job_id]
    assert job["status"] == "queued"
    assert job["cmd"][job["cmd"].index("-i") + 1] == str(output / "source.mp4")
    assert (output / ".transcript_checkpoint.json").read_text() == "checkpoint"
    assert json.loads((output / ".resume.json").read_text())["retry"] is True
    assert app_module.jobs_db.get_job(job_id)["status"] == "queued"
    assert _post(job_id).status_code == 409


def test_retry_missing_working_files_has_clear_error(setup_retry):
    job_id, output = setup_retry
    for item in output.iterdir():
        item.unlink()
    output.rmdir()
    result = _post(job_id)
    assert result.status_code == 410
    assert "expired" in result.json()["detail"]


def test_interrupted_retry_is_requeued_even_after_metadata_exists(setup_retry):
    job_id, output = setup_retry
    assert _post(job_id).status_code == 200
    (output / "source_metadata.json").write_text(json.dumps({"shorts": []}))
    app_module.jobs.clear()
    app_module._recover_jobs_from_disk()
    assert job_id not in app_module.jobs
    app_module._resume_interrupted_jobs()
    assert app_module.jobs[job_id]["status"] == "queued"
    assert (output / ".resume.json").exists()


def test_failed_old_metadata_does_not_disguise_failed_job(setup_retry):
    job_id, output = setup_retry
    (output / "source_metadata.json").write_text(json.dumps({"shorts": []}))
    app_module._recover_jobs_from_disk()
    assert job_id not in app_module.jobs
