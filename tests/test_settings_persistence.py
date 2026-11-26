import pytest

import jobs_db


def test_settings_survive_reopening_and_clear_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_db, "_DB_PATH", str(tmp_path / "jobs.db"))
    jobs_db.init_db()
    jobs_db.save_settings({"gemini_key": "test-key", "upload_user_id": "profile"})
    assert jobs_db.get_all_settings(strict=True) == {
        "gemini_key": "test-key", "upload_user_id": "profile"
    }
    with pytest.raises(ValueError):
        jobs_db.save_settings({"gemini_key": "new-key", "unknown": "value"})
    assert jobs_db.get_setting("gemini_key") == "test-key"
    jobs_db.save_settings({"gemini_key": ""})
    assert jobs_db.get_setting("gemini_key") is None


def test_settings_read_failure_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_db, "_DB_PATH", str(tmp_path / "directory"))
    (tmp_path / "directory").mkdir()
    with pytest.raises(Exception):
        jobs_db.get_all_settings(strict=True)
