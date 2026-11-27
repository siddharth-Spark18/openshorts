import jobs_db
import source_automation as automation


def setup_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    jobs_db.init_db()
    jobs_db.save_settings({'source_topics': 'GTA 6'})
    with jobs_db._conn() as con:
        con.execute("INSERT INTO source_channels VALUES ('channel', 'https://youtube.com/@channel', '2026')")
        con.execute("INSERT INTO source_videos VALUES ('abcdefghijk','channel','GTA VI news','2026-11-26T00:00:00Z','2026')")
        con.execute("INSERT INTO source_videos VALUES ('12345678901','channel','GTA 6 trailer','2026-11-27T00:00:00Z','2026')")


def test_claim_is_exclusive_retryable_and_rate_limited(tmp_path, monkeypatch):
    setup_sources(tmp_path, monkeypatch)
    claim = automation.claim_candidate()
    assert claim['video_id'] == '12345678901'
    assert automation.claim_candidate() is None
    automation.finish_claim(claim['video_id'], 'pending', 'wrong-owner')
    assert automation.claim_candidate() is None
    automation.finish_claim(claim['video_id'], 'pending', claim['lease_owner'])
    retry = automation.claim_candidate()
    assert retry['job_id'] == claim['job_id']
    automation.finish_claim(retry['video_id'], 'submitted', retry['lease_owner'])
    assert automation.claim_candidate() is None


def test_existing_manual_job_and_pause_are_respected(tmp_path, monkeypatch):
    setup_sources(tmp_path, monkeypatch)
    with jobs_db._conn() as con:
        con.execute("INSERT INTO jobs (job_id,status,input_source) VALUES ('manual','completed',?)",
                    ('https://youtu.be/12345678901?t=2',))
    jobs_db.save_settings({'source_auto_enabled': '0'})
    assert automation.claim_candidate() is None
    jobs_db.save_settings({'source_auto_enabled': '1'})
    assert automation.claim_candidate()['video_id'] == 'abcdefghijk'
