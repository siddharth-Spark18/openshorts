import asyncio
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import factory_schedule
import factory_youtube
import jobs_db


def test_queue_persists_spaced_slots_and_only_publishes_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    jobs_db.init_db()
    project, one, two = str(uuid4()), str(uuid4()), str(uuid4())
    with jobs_db._conn() as con:
        con.execute("INSERT INTO factory_channels VALUES (?,?,?,?)", (project, 'Office', 'workplace_skits', 'now'))
        con.execute("INSERT INTO factory_project_settings VALUES (?,?,?,?)", (project, '', 3, 'automatic'))
        for idea in (one, two):
            con.execute("INSERT INTO factory_ideas VALUES (?,?,?,'approved','now','now')", (idea, project, 'A funny meeting'))
            con.execute("INSERT INTO factory_scripts VALUES (?,?,'approved',1,'now')", (idea, 'Boss: Hello.'))
            con.execute("INSERT INTO factory_review_queue VALUES (?,1,'approved','now')", (idea,))
            factory_schedule.schedule_approved(con, idea, 1)
        slots = con.execute("SELECT * FROM factory_publish_queue WHERE platform='youtube' ORDER BY scheduled_at").fetchall()
        assert (datetime.fromisoformat(slots[1]['scheduled_at']) - datetime.fromisoformat(slots[0]['scheduled_at'])).total_seconds() == 8 * 3600
        factory_schedule.schedule_approved(con, one, 1)
        assert con.execute('SELECT COUNT(*) AS n FROM factory_publish_queue').fetchone()['n'] == 4
    factory_youtube.write_connection(tmp_path, project, {'refresh_token': 'token', 'channel_id': 'channel'})
    calls = []
    async def publish(idea_id, revision):
        calls.append((str(idea_id), revision))
    app = SimpleNamespace(state=SimpleNamespace(factory_youtube_publish=publish))
    library = SimpleNamespace(root=tmp_path)
    assert asyncio.run(factory_schedule.process_next(app, library))
    assert calls == [(one, 1)]
    assert not asyncio.run(factory_schedule.process_next(app, library))
    with jobs_db._conn() as con:
        assert con.execute("SELECT status FROM factory_publish_queue WHERE idea_id=? AND platform='youtube'", (one,)).fetchone()['status'] == 'published'


def test_manual_mode_and_missing_connection_do_not_publish(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_db, '_DB_PATH', str(tmp_path / 'jobs.db'))
    jobs_db.init_db()
    project, idea = str(uuid4()), str(uuid4())
    with jobs_db._conn() as con:
        con.execute("INSERT INTO factory_channels VALUES (?,?,?,?)", (project, 'Office', 'workplace_skits', 'now'))
        con.execute("INSERT INTO factory_project_settings VALUES (?,?,?,?)", (project, '', 1, 'automatic'))
        con.execute("INSERT INTO factory_ideas VALUES (?,?,?,'approved','now','now')", (idea, project, 'A funny meeting'))
        con.execute("INSERT INTO factory_scripts VALUES (?,?,'approved',1,'now')", (idea, 'Boss: Hello.'))
        con.execute("INSERT INTO factory_review_queue VALUES (?,1,'approved','now')", (idea,))
        factory_schedule.schedule_approved(con, idea, 1)
    app = SimpleNamespace(state=SimpleNamespace())
    library = SimpleNamespace(root=tmp_path)
    assert not asyncio.run(factory_schedule.process_next(app, library))
    factory_youtube.write_connection(tmp_path, project, {'refresh_token': 'token'})
    with jobs_db._conn() as con:
        con.execute("UPDATE factory_project_settings SET publishing_mode='manual' WHERE channel_id=?", (project,))
    assert not asyncio.run(factory_schedule.process_next(app, library))
