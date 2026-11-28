"""Durable, single-claim queue for approved social videos."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException

import factory_youtube
import factory_instagram
import jobs_db


def now_utc():
    return datetime.now(timezone.utc)


def schedule_approved(con, idea_id, revision):
    row = con.execute("SELECT i.channel_id,p.daily_target,p.publishing_mode FROM factory_ideas i "
                      "JOIN factory_project_settings p ON p.channel_id=i.channel_id WHERE i.id=?", (idea_id,)).fetchone()
    if not row or row['publishing_mode'] != 'automatic':
        return
    for platform in ('youtube', 'instagram'):
        publication = con.execute('SELECT status FROM factory_publications WHERE idea_id=? AND revision=? AND platform=?',
                                  (idea_id, revision, platform)).fetchone()
        if publication and publication['status'] in {'published', 'preparing', 'uploading', 'uncertain'}:
            continue
        existing = con.execute("SELECT status FROM factory_publish_queue WHERE idea_id=? AND revision=? AND platform=?", (idea_id, revision, platform)).fetchone()
        if existing and existing['status'] != 'cancelled':
            continue
        latest = con.execute("SELECT MAX(scheduled_at) AS last FROM factory_publish_queue WHERE channel_id=? AND platform=? AND status IN ('pending','processing','published')", (row['channel_id'], platform)).fetchone()['last']
        due = now_utc()
        if latest:
            due = max(due, datetime.fromisoformat(latest) + timedelta(hours=24 / row['daily_target']))
        con.execute("INSERT INTO factory_publish_queue VALUES (?,?,?,?,?,'pending',NULL,?) "
                    "ON CONFLICT(idea_id,revision,platform) DO UPDATE SET scheduled_at=excluded.scheduled_at,status='pending',error=NULL,updated_at=excluded.updated_at "
                    "WHERE factory_publish_queue.status='cancelled'", (idea_id, revision, row['channel_id'], platform, due.isoformat(), jobs_db._utcnow()))


async def process_next(app, library):
    with jobs_db._conn() as con:
        con.execute('BEGIN IMMEDIATE')
        rows = con.execute("SELECT q.*,p.daily_target FROM factory_publish_queue q "
            "JOIN factory_project_settings p ON p.channel_id=q.channel_id "
            "JOIN factory_ideas i ON i.id=q.idea_id AND i.status='approved' "
            "JOIN factory_scripts s ON s.idea_id=i.id AND s.revision=q.revision AND s.status='approved' "
            "JOIN factory_review_queue r ON r.idea_id=i.id AND r.revision=q.revision AND r.status='approved' "
            "WHERE q.status='pending' AND p.publishing_mode='automatic' AND q.scheduled_at<=? "
            "ORDER BY q.scheduled_at", (now_utc().isoformat(),)).fetchall()
        chosen = None
        for row in rows:
            connection = (factory_youtube.read_connection(library.root, row['channel_id']) if row['platform'] == 'youtube'
                          else factory_instagram.read_connection(library.root, row['channel_id']))
            if not connection.get('refresh_token' if row['platform'] == 'youtube' else 'access_token'):
                continue
            last = con.execute("SELECT MAX(updated_at) AS last FROM factory_publish_queue WHERE channel_id=? AND platform=? AND status='published'", (row['channel_id'], row['platform'])).fetchone()['last']
            if last and datetime.fromisoformat(last) + timedelta(hours=24 / row['daily_target']) > now_utc():
                continue
            chosen = row
            break
        if not chosen:
            return False
        con.execute("UPDATE factory_publish_queue SET status='processing',updated_at=? WHERE idea_id=? AND revision=? AND platform=? AND status='pending'",
                    (jobs_db._utcnow(), chosen['idea_id'], chosen['revision'], chosen['platform']))
    try:
        publisher = app.state.factory_youtube_publish if chosen['platform'] == 'youtube' else app.state.factory_instagram_publish
        await publisher(UUID(chosen['idea_id']), chosen['revision'])
        status, error = 'published', None
    except HTTPException as exc:
        status, error = 'failed', str(exc.detail)
    except Exception:
        status, error = 'failed', 'Publishing was interrupted. Check the destination account.'
    with jobs_db._conn() as con:
        con.execute("UPDATE factory_publish_queue SET status=?,error=?,updated_at=? WHERE idea_id=? AND revision=? AND platform=? AND status='processing'",
                    (status, error, jobs_db._utcnow(), chosen['idea_id'], chosen['revision'], chosen['platform']))
    return True


async def worker(app, library, can_run):
    while True:
        if can_run():
            try:
                await process_next(app, library)
            except Exception as exc:
                print(f'Factory queue error: {type(exc).__name__}')
        await asyncio.sleep(30)
