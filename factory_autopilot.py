"""Bounded project production: one original workplace skit at a time."""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jobs_db
from fastapi import HTTPException
import factory_instagram
import factory_youtube


async def produce_next(app):
    import factory_render
    import factory_story

    key = jobs_db.get_setting('gemini_key') or os.getenv('GEMINI_API_KEY')
    if not key or app.state.factory_render_active:
        return False
    guard = getattr(app.state, 'factory_render_guard', None)
    if guard and not guard():
        return False
    with jobs_db._conn() as con:
        con.execute('BEGIN IMMEDIATE')
        stale_before = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(timespec='seconds')
        con.execute("UPDATE factory_auto_state SET status='failed',error='Production was interrupted. Retry to continue.',updated_at=? "
                    "WHERE status='generating' AND updated_at<?", (jobs_db._utcnow(), stale_before))
        if con.execute("SELECT 1 FROM factory_auto_state WHERE status IN ('generating','rendering') LIMIT 1").fetchone():
            return False
        rows = con.execute("SELECT c.id,p.style,p.daily_target,COALESCE(a.status,'idle') AS auto_status "
                           "FROM factory_channels c JOIN factory_project_settings p ON p.channel_id=c.id "
                           "LEFT JOIN factory_auto_state a ON a.channel_id=c.id "
                           "WHERE c.content_type='workplace_skits' AND p.publishing_mode='automatic' ORDER BY c.created_at").fetchall()
        chosen = None
        for row in rows:
            if row['auto_status'] == 'failed':
                continue
            youtube = factory_youtube.read_connection(app.state.factory_library.root, row['id'])
            instagram = factory_instagram.read_connection(app.state.factory_library.root, row['id'])
            connected = [platform for platform, ready in (('youtube', bool(youtube.get('refresh_token'))),
                         ('instagram', bool(instagram.get('access_token')))) if ready]
            if connected:
                buffered = con.execute("SELECT COUNT(DISTINCT idea_id) AS n FROM factory_publish_queue WHERE channel_id=? AND status IN ('pending','processing') AND platform IN (%s)" % ','.join('?' for _ in connected), (row['id'], *connected)).fetchone()['n']
            else:
                buffered = con.execute("SELECT COUNT(DISTINCT idea_id) AS n FROM factory_publish_queue WHERE channel_id=? AND status IN ('pending','processing')", (row['id'],)).fetchone()['n']
            if buffered < row['daily_target']:
                chosen = row
                break
        if not chosen:
            return False
        con.execute("INSERT INTO factory_auto_state VALUES (?,'generating',NULL,?) ON CONFLICT(channel_id) DO UPDATE SET status='generating',error=NULL,updated_at=excluded.updated_at",
                    (chosen['id'], jobs_db._utcnow()))
        unfinished = con.execute("SELECT i.id FROM factory_auto_ideas a JOIN factory_ideas i ON i.id=a.idea_id "
            "JOIN factory_scripts s ON s.idea_id=i.id AND s.status='approved' "
            "LEFT JOIN factory_renders r ON r.idea_id=i.id AND r.revision=s.revision "
            "WHERE a.channel_id=? AND i.status='approved' AND r.idea_id IS NULL ORDER BY a.created_at LIMIT 1", (chosen['id'],)).fetchone()
    try:
        if unfinished:
            idea_id = unfinished['id']
        else:
            ideas = await asyncio.to_thread(factory_story.generate_ideas, chosen['style'], 1, key)
            source = ideas[0] + ('\n\nDesired project style: ' + chosen['style'] if chosen['style'] else '')
            script = await asyncio.to_thread(factory_story.generate_script, source, key)
            factory_render.dialogue_lines(script)
            idea_id, now = str(uuid4()), jobs_db._utcnow()
            with jobs_db._conn() as con:
                con.execute('BEGIN IMMEDIATE')
                still_auto = con.execute("SELECT 1 FROM factory_project_settings WHERE channel_id=? AND publishing_mode='automatic'", (chosen['id'],)).fetchone()
                if not still_auto:
                    con.execute("UPDATE factory_auto_state SET status='idle',updated_at=? WHERE channel_id=?", (jobs_db._utcnow(), chosen['id']))
                    return False
                con.execute("INSERT INTO factory_ideas VALUES (?,?,?,'approved',?,?)", (idea_id, chosen['id'], ideas[0], now, now))
                con.execute("INSERT INTO factory_scripts VALUES (?,?,'approved',1,?)", (idea_id, script, now))
                con.execute('INSERT INTO factory_auto_ideas VALUES (?,?,?)', (idea_id, chosen['id'], now))
        with jobs_db._conn() as con:
            con.execute("UPDATE factory_auto_state SET status='rendering',updated_at=? WHERE channel_id=?", (jobs_db._utcnow(), chosen['id']))
        await app.state.factory_render_skit(UUID(idea_id))
        return True
    except HTTPException as exc:
        with jobs_db._conn() as con:
            con.execute("UPDATE factory_auto_state SET status=?,error=?,updated_at=? WHERE channel_id=?",
                        ('idle' if exc.status_code == 409 else 'failed', None if exc.status_code == 409 else str(exc.detail), jobs_db._utcnow(), chosen['id']))
        return False
    except Exception as exc:
        print(f'Automatic production failed: {type(exc).__name__}')
        with jobs_db._conn() as con:
            con.execute("UPDATE factory_auto_state SET status='failed',error=?,updated_at=? WHERE channel_id=?",
                        ('Automatic production stopped. Check your Gemini key, storage, and server logs, then retry.', jobs_db._utcnow(), chosen['id']))
        return False


async def worker(app, can_run):
    while True:
        if can_run():
            try:
                await produce_next(app)
            except Exception as exc:
                print(f'Automatic production worker failed: {type(exc).__name__}')
        await asyncio.sleep(30)
