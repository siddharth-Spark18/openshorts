"""Private single-owner session and persistent finished-clip library."""
import hmac
import asyncio
import os
import json
import secrets
import shutil
import tempfile
import time
from pathlib import Path
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from urllib.parse import urlsplit, quote
from pydantic import BaseModel
import re
import sqlite3
from datetime import datetime, timezone
import jobs_db
import httpx

from fastapi import File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse

COOKIE = "openshorts_owner"
SESSION_SECONDS = 12 * 3600
LOGIN_PAGE = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Sign in · OpenShorts</title>
<style>*{box-sizing:border-box}body{background:#181917;color:#eeeae3;font:16px system-ui;margin:0;
min-height:100svh;display:grid;place-items:center}main{width:min(24rem,90vw)}h1{font:36px Georgia}
label,input,button{display:block;width:100%}input,button{padding:12px;border:1px solid #89877e;
border-radius:6px;margin-top:8px;font:inherit}button{margin-top:20px;cursor:pointer;background:#e7d5a4}
p{color:#efae95}</style><main><small>OpenShorts</small><h1>Private workspace</h1>
<form method="post" action="/owner/login"><label>Password<input type="password" name="password"
autocomplete="current-password" autofocus required></label>MESSAGE<button>Sign in</button></form></main></html>"""


class ClipLibrary:
    def __init__(self, directory):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)

    def archive(self, job_id, job):
        if job.get("status") != "completed":
            return
        destination = self.root / str(UUID(job_id))
        if destination.exists():
            return  # Also remembers deletions when recovering a working job.
        source = Path(job["output_dir"]).resolve()
        with tempfile.TemporaryDirectory(dir=self.root, prefix=".save-") as temp:
            stage = Path(temp) / "clips"
            stage.mkdir()
            entries = []
            for clip in job["result"]["clips"]:
                name = Path(clip.get("video_url", "")).name
                path = source / name
                if path.is_symlink() or not path.is_file() or not path.stat().st_size:
                    continue
                index = len(entries)
                shutil.copyfile(path, stage / f"{index}.mp4")
                entries.append({"index": index, "title": clip.get("video_title_for_youtube_short")
                                or clip.get("title") or name, "filename": name,
                                "review_warning": clip.get("review_warning")})
            if entries:
                (stage / "index.json").write_text(json.dumps(entries))
                stage.rename(destination)

    def clips(self):
        rows = []
        for manifest in sorted(self.root.glob("*/index.json"),
                               key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                receipts = json.loads((manifest.parent / ".drive-receipts.json").read_text())
            except (FileNotFoundError, ValueError):
                receipts = {}
            for entry in json.loads(manifest.read_text()):
                path = manifest.parent / f"{entry['index']}.mp4"
                key = f"{manifest.parent.name}-{entry['index']}"
                receipt = receipts.get(key) or {}
                if path.is_file() or receipt.get("id"):
                    rows.append({**entry, "job_id": manifest.parent.name})
        return rows


def install(app, password, library):
    sessions = {}

    @app.middleware("http")
    async def require_owner(request: Request, call_next):
        public = {"/owner/login", "/health/ready", "/health/live", "/health/deployment"}
        media_grant = request.method in {'GET', 'HEAD'} and re.fullmatch(r'/api/factory/media/[A-Za-z0-9_-]{43}', request.url.path)
        if request.url.path not in public and not media_grant:
            token = request.cookies.get(COOKIE, "")
            if sessions.get(token, 0) <= time.monotonic():
                return JSONResponse({"detail": "Sign in to OpenShorts."}, status_code=401,
                                    headers={"X-OpenShorts-Login": "required"})
        return await call_next(request)

    @app.get("/owner/check")
    def check():
        return Response(status_code=204)

    @app.get("/owner/login")
    def login_form():
        return HTMLResponse(LOGIN_PAGE.replace("MESSAGE", ""), headers={"Cache-Control": "no-store"})

    @app.post("/owner/login")
    async def login(request: Request, password_input: str = Form(alias="password")):
        if not hmac.compare_digest(password.encode(), password_input.encode()):
            return HTMLResponse(LOGIN_PAGE.replace("MESSAGE", "<p>Incorrect password.</p>"), status_code=401)
        now = time.monotonic()
        for token in list(sessions):
            if sessions[token] <= now:
                del sessions[token]
        token = secrets.token_urlsafe(32)
        sessions[token] = now + SESSION_SECONDS
        response = RedirectResponse("/#app", status_code=303)
        response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                            secure=request.url.scheme == "https", samesite="lax")
        return response

    @app.post("/owner/logout")
    async def logout(request: Request):
        sessions.pop(request.cookies.get(COOKIE, ""), None)
        response = RedirectResponse("/owner/login", status_code=303)
        response.delete_cookie(COOKIE)
        return response

    @app.get("/api/youtube-cookies")
    def cookie_status():
        path = os.environ.get("YOUTUBE_COOKIES_PATH")
        return {"configured": bool(path and Path(path).is_file())}

    @app.put("/api/youtube-cookies")
    async def save_cookies(file: UploadFile = File(...)):
        path = os.environ.get("YOUTUBE_COOKIES_PATH")
        if not path:
            raise HTTPException(503, "YouTube cookie storage is not configured.")
        contents = await file.read(1024 * 1024 + 1)
        if len(contents) > 1024 * 1024:
            raise HTTPException(400, "Cookie file must be under 1 MB.")
        try:
            lines = contents.decode("utf-8-sig").splitlines()
        except UnicodeDecodeError:
            raise HTTPException(400, "Cookie file must be UTF-8 text.")
        domains = [line.split("\t", 1)[0].removeprefix("#HttpOnly_").lstrip(".")
                   for line in lines if "\t" in line]
        if not lines or "Netscape HTTP Cookie File" not in lines[0] or not any(
            domain == "youtube.com" or domain.endswith(".youtube.com") for domain in domains
        ):
            raise HTTPException(400, "Upload a Netscape-format cookie file containing YouTube cookies.")
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
            temporary.write(contents)
            temp_path = Path(temporary.name)
        try:
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, destination)
        finally:
            temp_path.unlink(missing_ok=True)
        return {"configured": True}

    @app.delete("/api/youtube-cookies")
    def delete_cookies():
        path = os.environ.get("YOUTUBE_COOKIES_PATH")
        if path:
            Path(path).unlink(missing_ok=True)
        return Response(status_code=204)

    import drive_connection
    drive_connection.install(app, library)

    import factory_youtube
    factory_youtube.install(app, library)
    import factory_instagram
    factory_instagram.install(app, library)

    factory_render_lock = asyncio.Lock()
    app.state.factory_render_active = False
    app.state.factory_library = library

    def ensure_not_publishing(con, idea_id):
        if (con.execute("SELECT 1 FROM factory_publications WHERE idea_id=? AND status IN ('preparing','uploading')", (str(idea_id),)).fetchone()
                or con.execute("SELECT 1 FROM factory_publish_queue WHERE idea_id=? AND status='processing'", (str(idea_id),)).fetchone()):
            raise HTTPException(409, 'Wait for publishing to finish before changing this video.')

    class FactoryChannel(BaseModel):
        name: str
        content_type: str

    class FactoryIdea(BaseModel):
        idea: str

    class FactoryIdeaStatus(BaseModel):
        status: str

    class FactoryIdeaBatch(BaseModel):
        count: int = 3

    class FactoryProjectSettings(BaseModel):
        style: str = ''
        daily_target: int = 1
        publishing_mode: str = 'manual'

    @app.get("/api/factory/channels")
    def list_factory_channels():
        with jobs_db._conn() as con:
            channels = [dict(row) for row in con.execute(
                "SELECT * FROM factory_channels ORDER BY created_at DESC, rowid DESC")]
            for channel in channels:
                settings = con.execute("SELECT style,daily_target,publishing_mode FROM factory_project_settings WHERE channel_id=?", (channel['id'],)).fetchone()
                channel['settings'] = dict(settings) if settings else {'style': '', 'daily_target': 1, 'publishing_mode': 'manual'}
                connection = factory_youtube.read_connection(library.root, channel['id'])
                instagram = factory_instagram.read_connection(library.root, channel['id'])
                channel['connections'] = {'youtube': {'connected': bool(connection.get('refresh_token')),
                    'channel_title': connection.get('channel_title'), 'channel_id': connection.get('channel_id'),
                    'available': all(factory_youtube.credentials())}, 'instagram': {
                        'connected': bool(instagram.get('access_token') and instagram.get('expires_at', 0) > time.time()),
                        'username': instagram.get('username'), 'available': all(factory_instagram.credentials())}}
                auto_state = con.execute('SELECT status,error FROM factory_auto_state WHERE channel_id=?', (channel['id'],)).fetchone()
                channel['auto_production'] = dict(auto_state) if auto_state else {'status': 'idle', 'error': None}
                channel["ideas"] = [dict(row) for row in con.execute(
                    "SELECT i.*, s.script, s.status AS script_status, s.revision AS script_revision, "
                    "CASE WHEN r.revision=s.revision AND s.status='approved' AND i.status='approved' THEN 1 ELSE 0 END AS video_ready, "
                    "j.status AS render_status, j.error AS render_error, "
                    "CASE WHEN q.revision=s.revision AND s.status='approved' AND i.status='approved' THEN q.status ELSE NULL END AS queue_status, "
                    "p.status AS youtube_publication_status, p.remote_id AS youtube_video_id, "
                    "pq.status AS schedule_status, pq.scheduled_at, "
                    "ip.status AS instagram_publication_status, ip.remote_id AS instagram_media_id, "
                    "iq.status AS instagram_schedule_status, iq.scheduled_at AS instagram_scheduled_at "
                    "FROM factory_ideas i LEFT JOIN factory_scripts s ON s.idea_id=i.id "
                    "LEFT JOIN factory_renders r ON r.idea_id=i.id "
                    "LEFT JOIN factory_render_jobs j ON j.idea_id=i.id "
                    "LEFT JOIN factory_review_queue q ON q.idea_id=i.id "
                    "LEFT JOIN factory_publications p ON p.idea_id=i.id AND p.revision=s.revision AND p.platform='youtube' "
                    "LEFT JOIN factory_publications ip ON ip.idea_id=i.id AND ip.revision=s.revision AND ip.platform='instagram' "
                    "LEFT JOIN factory_publish_queue pq ON pq.idea_id=i.id AND pq.revision=s.revision AND pq.platform='youtube' "
                    "LEFT JOIN factory_publish_queue iq ON iq.idea_id=i.id AND iq.revision=s.revision AND iq.platform='instagram' "
                    "WHERE i.channel_id=? ORDER BY i.created_at DESC, i.rowid DESC",
                    (channel["id"],))]
        return {"channels": channels}

    @app.post("/api/factory/channels", status_code=201)
    def create_factory_channel(body: FactoryChannel):
        name = body.name.strip()
        if not name or len(name) > 100 or body.content_type not in {"gaming_clips", "workplace_skits"}:
            raise HTTPException(400, "Enter a name and choose a content type.")
        row = {"id": str(uuid4()), "name": name, "content_type": body.content_type,
               "created_at": jobs_db._utcnow()}
        with jobs_db._conn() as con:
            con.execute("INSERT INTO factory_channels VALUES (:id,:name,:content_type,:created_at)", row)
        return row

    @app.put('/api/factory/channels/{channel_id}/settings')
    def update_factory_settings(channel_id: UUID, body: FactoryProjectSettings):
        style = body.style.strip()
        if len(style) > 2000 or not 1 <= body.daily_target <= 20 or body.publishing_mode not in {'manual', 'automatic'}:
            raise HTTPException(400, 'Choose a valid publishing mode, daily target (1–20), and style (up to 2,000 characters).')
        with jobs_db._conn() as con:
            if not con.execute('SELECT 1 FROM factory_channels WHERE id=?', (str(channel_id),)).fetchone():
                raise HTTPException(404, 'Project not found.')
            con.execute('INSERT INTO factory_project_settings (channel_id,style,daily_target,publishing_mode) VALUES (?,?,?,?) '
                        'ON CONFLICT(channel_id) DO UPDATE SET style=excluded.style,daily_target=excluded.daily_target,publishing_mode=excluded.publishing_mode',
                        (str(channel_id), style, body.daily_target, body.publishing_mode))
            if body.publishing_mode == 'automatic':
                from factory_schedule import schedule_approved
                approved = con.execute("SELECT i.id,s.revision FROM factory_ideas i JOIN factory_scripts s ON s.idea_id=i.id "
                    "JOIN factory_review_queue q ON q.idea_id=i.id AND q.revision=s.revision "
                    "WHERE i.channel_id=? AND i.status='approved' AND s.status='approved' AND q.status='approved'", (str(channel_id),)).fetchall()
                for idea in approved:
                    schedule_approved(con, idea['id'], idea['revision'])
        return {'style': style, 'daily_target': body.daily_target, 'publishing_mode': body.publishing_mode}

    @app.post('/api/factory/channels/{channel_id}/production/retry')
    def retry_factory_production(channel_id: UUID):
        with jobs_db._conn() as con:
            changed = con.execute("UPDATE factory_auto_state SET status='idle',error=NULL,updated_at=? WHERE channel_id=? AND status='failed'",
                                  (jobs_db._utcnow(), str(channel_id)))
            if not changed.rowcount:
                raise HTTPException(409, 'There is no failed production to retry.')
        return {'status': 'idle'}

    @app.post("/api/factory/channels/{channel_id}/ideas", status_code=201)
    def create_factory_idea(channel_id: UUID, body: FactoryIdea):
        idea = body.idea.strip()
        if not idea or len(idea) > 2000:
            raise HTTPException(400, "Enter an idea of up to 2,000 characters.")
        now = jobs_db._utcnow()
        row = {"id": str(uuid4()), "channel_id": str(channel_id), "idea": idea,
               "status": "needs_review", "created_at": now, "updated_at": now}
        with jobs_db._conn() as con:
            if not con.execute("SELECT 1 FROM factory_channels WHERE id=?", (str(channel_id),)).fetchone():
                raise HTTPException(404, "Channel not found.")
            con.execute("INSERT INTO factory_ideas VALUES (:id,:channel_id,:idea,:status,:created_at,:updated_at)", row)
        return row

    @app.post('/api/factory/channels/{channel_id}/ideas/generate', status_code=201)
    async def generate_factory_ideas(channel_id: UUID, body: FactoryIdeaBatch):
        import factory_story
        if not 1 <= body.count <= 5:
            raise HTTPException(400, 'Choose between one and five ideas.')
        with jobs_db._conn() as con:
            channel = con.execute("SELECT c.name,c.content_type,COALESCE(p.style,'') AS style FROM factory_channels c "
                                  "LEFT JOIN factory_project_settings p ON p.channel_id=c.id WHERE c.id=?", (str(channel_id),)).fetchone()
        if not channel:
            raise HTTPException(404, 'Project not found.')
        if channel['content_type'] != 'workplace_skits':
            raise HTTPException(400, 'Idea generation is currently available for workplace skits.')
        api_key = jobs_db.get_setting('gemini_key') or os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise HTTPException(400, 'Add a Gemini API key in Settings first.')
        try:
            ideas = await asyncio.to_thread(factory_story.generate_ideas, channel['style'], body.count, api_key)
        except Exception as exc:
            print(f'Idea generation failed: {type(exc).__name__}')
            raise HTTPException(502, 'Could not generate ideas. Check your Gemini connection and try again.') from exc
        now = jobs_db._utcnow()
        rows = [{'id': str(uuid4()), 'channel_id': str(channel_id), 'idea': idea, 'status': 'needs_review',
                 'created_at': now, 'updated_at': now} for idea in ideas]
        with jobs_db._conn() as con:
            con.execute('BEGIN IMMEDIATE')
            if not con.execute('SELECT 1 FROM factory_channels WHERE id=?', (str(channel_id),)).fetchone():
                raise HTTPException(404, 'Project no longer exists.')
            con.executemany('INSERT INTO factory_ideas VALUES (:id,:channel_id,:idea,:status,:created_at,:updated_at)', rows)
        return {'ideas': rows}

    @app.patch("/api/factory/ideas/{idea_id}")
    def update_factory_idea(idea_id: UUID, body: FactoryIdeaStatus):
        if body.status not in {"needs_review", "approved", "rejected"}:
            raise HTTPException(400, "Invalid review status.")
        with jobs_db._conn() as con:
            con.execute('BEGIN IMMEDIATE')
            ensure_not_publishing(con, idea_id)
            result = con.execute("UPDATE factory_ideas SET status=?, updated_at=? WHERE id=?",
                                 (body.status, jobs_db._utcnow(), str(idea_id)))
            if not result.rowcount:
                raise HTTPException(404, "Idea not found.")
            if body.status != "approved":
                con.execute("UPDATE factory_scripts SET status='needs_review',revision=revision+1,updated_at=? WHERE idea_id=?",
                            (jobs_db._utcnow(), str(idea_id)))
                con.execute("UPDATE factory_publish_queue SET status='cancelled',updated_at=? WHERE idea_id=? AND status='pending'", (jobs_db._utcnow(), str(idea_id)))
        return {"id": str(idea_id), "status": body.status}

    class FactoryScript(BaseModel):
        script: str
        revision: int

    class FactoryScriptReview(BaseModel):
        status: str
        revision: int

    @app.post("/api/factory/ideas/{idea_id}/script")
    async def generate_factory_script(idea_id: UUID):
        import factory_story
        with jobs_db._conn() as con:
            idea = con.execute(
                "SELECT i.idea,i.status,c.content_type, COALESCE(p.style, '') AS style FROM factory_ideas i "
                "JOIN factory_channels c ON c.id=i.channel_id LEFT JOIN factory_project_settings p ON p.channel_id=c.id WHERE i.id=?", (str(idea_id),)).fetchone()
            previous = con.execute("SELECT revision FROM factory_scripts WHERE idea_id=?", (str(idea_id),)).fetchone()
        if not idea:
            raise HTTPException(404, "Idea not found.")
        if idea["content_type"] != "workplace_skits" or idea["status"] != "approved":
            raise HTTPException(400, "Approve a workplace skit idea before generating its script.")
        api_key = jobs_db.get_setting("gemini_key") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(400, "Add a Gemini API key in Settings first.")
        revision = previous["revision"] if previous else 0
        try:
            prompt_idea = idea['idea']
            if idea['style']:
                prompt_idea += '\n\nDesired project style: ' + idea['style']
            script = await asyncio.to_thread(factory_story.generate_script, prompt_idea, api_key)
        except Exception as exc:
            print(f"Script generation failed: {type(exc).__name__}")
            raise HTTPException(502, "Could not generate the script. Check your Gemini connection and try again.") from exc
        with jobs_db._conn() as con:
            con.execute("BEGIN IMMEDIATE")
            ensure_not_publishing(con, idea_id)
            current = con.execute("SELECT revision FROM factory_scripts WHERE idea_id=?", (str(idea_id),)).fetchone()
            still_approved = con.execute("SELECT status FROM factory_ideas WHERE id=?", (str(idea_id),)).fetchone()
            if (current["revision"] if current else 0) != revision or not still_approved or still_approved["status"] != "approved":
                raise HTTPException(409, "The idea or script changed while generating. Try again.")
            con.execute("INSERT INTO factory_scripts VALUES (?,?,?,?,?) ON CONFLICT(idea_id) DO UPDATE SET "
                        "script=excluded.script,status=excluded.status,revision=excluded.revision,updated_at=excluded.updated_at",
                        (str(idea_id), script, "needs_review", revision + 1, jobs_db._utcnow()))
            con.execute("UPDATE factory_publish_queue SET status='cancelled',updated_at=? WHERE idea_id=? AND status='pending'", (jobs_db._utcnow(), str(idea_id)))
        return {"script": script, "status": "needs_review", "revision": revision + 1}

    @app.put("/api/factory/ideas/{idea_id}/script")
    def edit_factory_script(idea_id: UUID, body: FactoryScript):
        script = body.script.strip()
        if not script or len(script) > 12000:
            raise HTTPException(400, "Enter a script of up to 12,000 characters.")
        with jobs_db._conn() as con:
            con.execute('BEGIN IMMEDIATE')
            ensure_not_publishing(con, idea_id)
            result = con.execute("UPDATE factory_scripts SET script=?,status='needs_review',revision=revision+1,updated_at=? "
                                 "WHERE idea_id=? AND revision=?", (script, jobs_db._utcnow(), str(idea_id), body.revision))
            if not result.rowcount:
                raise HTTPException(409, "The script changed. Refresh and try again.")
            con.execute("UPDATE factory_publish_queue SET status='cancelled',updated_at=? WHERE idea_id=? AND status='pending'", (jobs_db._utcnow(), str(idea_id)))
        return {"script": script, "status": "needs_review", "revision": body.revision + 1}

    @app.patch("/api/factory/ideas/{idea_id}/script/review")
    def review_factory_script(idea_id: UUID, body: FactoryScriptReview):
        if body.status not in {"approved", "rejected", "needs_review"}:
            raise HTTPException(400, "Invalid review status.")
        with jobs_db._conn() as con:
            con.execute('BEGIN IMMEDIATE')
            ensure_not_publishing(con, idea_id)
            result = con.execute("UPDATE factory_scripts SET status=?,revision=revision+1,updated_at=? "
                                 "WHERE idea_id=? AND revision=? AND EXISTS "
                                 "(SELECT 1 FROM factory_ideas WHERE id=? AND status='approved')",
                                 (body.status, jobs_db._utcnow(), str(idea_id), body.revision, str(idea_id)))
            if not result.rowcount:
                raise HTTPException(409, "The script changed or its idea is no longer approved. Refresh and try again.")
            con.execute("UPDATE factory_publish_queue SET status='cancelled',updated_at=? WHERE idea_id=? AND status='pending'", (jobs_db._utcnow(), str(idea_id)))
        return {"status": body.status, "revision": body.revision + 1}

    async def _run_factory_skit(idea_id, revision, script, output):
        import factory_render
        status, error = 'failed', 'Rendering was interrupted. Try again.'
        try:
            await asyncio.to_thread(factory_render.render, script, output)
            with jobs_db._conn() as con:
                con.execute("BEGIN IMMEDIATE")
                current = con.execute("SELECT s.revision FROM factory_scripts s JOIN factory_ideas i ON i.id=s.idea_id "
                                      "WHERE s.idea_id=? AND s.status='approved' AND i.status='approved'", (idea_id,)).fetchone()
                if not current or current['revision'] != revision:
                    output.unlink(missing_ok=True)
                    error = 'The script changed during rendering. Approve it and render again.'
                else:
                    archive_id = str(uuid5(NAMESPACE_URL, f"openshorts:factory:{idea_id}:{revision}"))
                    library.archive(archive_id, {"status": "completed", "output_dir": output.parent,
                        "result": {"clips": [{"title": "Workplace skit", "video_url": f"/videos/{archive_id}/{output.name}"}]}})
                    if not (library.root / archive_id / 'index.json').is_file():
                        raise RuntimeError("Could not save skit to the clip library")
                    con.execute("INSERT INTO factory_renders VALUES (?,?,?) ON CONFLICT(idea_id) DO UPDATE SET "
                                "revision=excluded.revision,created_at=excluded.created_at", (idea_id, revision, jobs_db._utcnow()))
                    automatic = con.execute("SELECT 1 FROM factory_auto_ideas a JOIN factory_project_settings p ON p.channel_id=a.channel_id "
                        "WHERE a.idea_id=? AND p.publishing_mode='automatic'", (idea_id,)).fetchone()
                    video_review = 'approved' if automatic else 'needs_review'
                    con.execute("INSERT INTO factory_review_queue VALUES (?,?,?,?) ON CONFLICT(idea_id) DO UPDATE SET "
                                "revision=excluded.revision,status=excluded.status,updated_at=excluded.updated_at",
                                (idea_id, revision, video_review, jobs_db._utcnow()))
                    if automatic:
                        from factory_schedule import schedule_approved
                        schedule_approved(con, idea_id, revision)
                    status, error = 'completed', None
        except Exception as exc:
            print(f"Skit render failed: {type(exc).__name__}")
            error = 'Could not render the skit. Check server logs and try again.'
        finally:
            try:
                with jobs_db._conn() as con:
                    con.execute("UPDATE factory_render_jobs SET status=?,error=?,updated_at=? WHERE idea_id=? AND revision=?",
                                (status, error, jobs_db._utcnow(), idea_id, revision))
                    auto_idea = con.execute('SELECT channel_id FROM factory_auto_ideas WHERE idea_id=?', (idea_id,)).fetchone()
                    if auto_idea:
                        con.execute("UPDATE factory_auto_state SET status=?,error=?,updated_at=? WHERE channel_id=?",
                            ('idle' if status == 'completed' else 'failed', error, jobs_db._utcnow(), auto_idea['channel_id']))
            finally:
                app.state.factory_render_active = False

    @app.post("/api/factory/ideas/{idea_id}/render", status_code=202)
    async def render_factory_skit(idea_id: UUID):
        import factory_render
        async with factory_render_lock:
            if app.state.factory_render_active:
                raise HTTPException(409, "Another skit is rendering. Try again when it finishes.")
            guard = getattr(app.state, 'factory_render_guard', None)
            if guard and not guard():
                raise HTTPException(409, "Wait for processing or deployment to finish before rendering a skit.")
            if shutil.disk_usage(library.root).free < 2 * 1024**3:
                raise HTTPException(507, 'At least 2 GB of free storage is needed to render a skit.')
            with jobs_db._conn() as con:
                con.execute('BEGIN IMMEDIATE')
                ensure_not_publishing(con, idea_id)
                row = con.execute("SELECT s.script,s.revision FROM factory_scripts s "
                                  "JOIN factory_ideas i ON i.id=s.idea_id "
                                  "WHERE s.idea_id=? AND s.status='approved' AND i.status='approved'", (str(idea_id),)).fetchone()
                active = con.execute("SELECT 1 FROM jobs WHERE status IN ('queued','processing') LIMIT 1").fetchone()
                if not row:
                    raise HTTPException(400, "Approve the idea and script before rendering.")
                if active:
                    raise HTTPException(409, "Wait for video processing to finish before rendering a skit.")
                try:
                    factory_render.dialogue_lines(row['script'])
                except ValueError as exc:
                    raise HTTPException(400, str(exc)) from exc
                con.execute("INSERT INTO factory_render_jobs VALUES (?,?,?,?,?) ON CONFLICT(idea_id) DO UPDATE SET "
                            "revision=excluded.revision,status=excluded.status,error=NULL,updated_at=excluded.updated_at",
                            (str(idea_id), row['revision'], 'processing', None, jobs_db._utcnow()))
                con.execute("UPDATE factory_review_queue SET status='needs_review',updated_at=? WHERE idea_id=? AND revision=?",
                            (jobs_db._utcnow(), str(idea_id), row['revision']))
                con.execute("UPDATE factory_publish_queue SET status='cancelled',updated_at=? WHERE idea_id=? AND revision=? AND status='pending'",
                            (jobs_db._utcnow(), str(idea_id), row['revision']))
            app.state.factory_render_active = True
            output = library.root / 'factory' / str(idea_id) / f'{row["revision"]}.mp4'
            asyncio.create_task(_run_factory_skit(str(idea_id), row['revision'], row['script'], output))
            return {"status": "processing"}

    app.state.factory_render_skit = render_factory_skit

    @app.get("/api/factory/ideas/{idea_id}/video")
    def factory_skit_video(idea_id: UUID):
        with jobs_db._conn() as con:
            row = con.execute("SELECT r.revision FROM factory_renders r JOIN factory_scripts s ON s.idea_id=r.idea_id "
                              "JOIN factory_ideas i ON i.id=s.idea_id WHERE r.idea_id=? AND r.revision=s.revision "
                              "AND s.status='approved' AND i.status='approved'", (str(idea_id),)).fetchone()
        path = library.root / 'factory' / str(idea_id) / f'{row["revision"]}.mp4' if row else None
        if not path or not path.is_file():
            raise HTTPException(404, "No current skit video is available.")
        return FileResponse(path, media_type='video/mp4', filename='workplace-skit.mp4')

    class FactoryVideoReview(BaseModel):
        status: str
        revision: int

    @app.put('/api/factory/ideas/{idea_id}/video/review')
    def review_factory_video(idea_id: UUID, body: FactoryVideoReview):
        if body.status not in {'needs_review', 'approved', 'rejected'}:
            raise HTTPException(400, 'Invalid video review status.')
        with jobs_db._conn() as con:
            con.execute('BEGIN IMMEDIATE')
            ensure_not_publishing(con, idea_id)
            row = con.execute("SELECT s.revision FROM factory_scripts s JOIN factory_ideas i ON i.id=s.idea_id "
                              "JOIN factory_renders r ON r.idea_id=s.idea_id AND r.revision=s.revision "
                              "WHERE i.id=? AND i.status='approved' AND s.status='approved'", (str(idea_id),)).fetchone()
            if con.execute("SELECT 1 FROM factory_render_jobs WHERE idea_id=? AND status='processing'", (str(idea_id),)).fetchone():
                raise HTTPException(409, 'Wait for rendering to finish before reviewing this video.')
            path = library.root / 'factory' / str(idea_id) / f'{body.revision}.mp4'
            if not row or row['revision'] != body.revision or not path.is_file():
                raise HTTPException(409, 'The video is missing or out of date. Render the current approved script first.')
            con.execute('INSERT INTO factory_review_queue VALUES (?,?,?,?) ON CONFLICT(idea_id) DO UPDATE SET '
                        'revision=excluded.revision,status=excluded.status,updated_at=excluded.updated_at',
                        (str(idea_id), body.revision, body.status, jobs_db._utcnow()))
            from factory_schedule import schedule_approved
            if body.status == 'approved':
                schedule_approved(con, str(idea_id), body.revision)
            else:
                con.execute("UPDATE factory_publish_queue SET status='cancelled',updated_at=? WHERE idea_id=? AND revision=? AND status='pending'",
                            (jobs_db._utcnow(), str(idea_id), body.revision))
        return {'status': body.status, 'revision': body.revision}

    class SourceChannel(BaseModel):
        url: str

    @app.get("/api/source-channels")
    def list_source_channels():
        with jobs_db._conn() as con:
            rows = con.execute(
                "SELECT c.id, c.url, c.created_at, s.checked_at, s.error "
                "FROM source_channels c LEFT JOIN source_channel_state s ON s.channel_id=c.id "
                "ORDER BY c.created_at DESC, c.rowid DESC"
            ).fetchall()
        return {"channels": [dict(row) for row in rows]}

    @app.post("/api/source-channels", status_code=201)
    def add_source_channel(channel: SourceChannel):
        try:
            parsed = urlsplit(channel.url.strip())
            host = (parsed.hostname or "").lower()
            parts = [part for part in parsed.path.split("/") if part]
            if (parsed.scheme != "https" or host not in {"youtube.com", "www.youtube.com", "m.youtube.com"}
                    or parsed.username or parsed.password or parsed.port
                    or not parts):
                raise ValueError()
            if parts[0].startswith("@") and len(parts[0]) > 1:
                path = parts[0]
            elif len(parts) >= 2 and parts[0] in {"channel", "c", "user"}:
                path = "/".join(parts[:2])
            else:
                raise ValueError()
            if any(not re.fullmatch(r"[A-Za-z0-9_@.\-]+", part) for part in path.split("/")):
                raise ValueError()
            url = "https://www.youtube.com/" + path
        except ValueError:
            raise HTTPException(400, "Enter a YouTube channel URL, such as youtube.com/@channel.")
        channel_id = str(uuid4())
        try:
            with jobs_db._conn() as con:
                con.execute("INSERT INTO source_channels (id, url, created_at) VALUES (?, ?, ?)",
                            (channel_id, url, jobs_db._utcnow()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "That channel is already in your list.")
        return {"id": channel_id, "url": url}

    @app.delete("/api/source-channels/{channel_id}", status_code=204)
    def delete_source_channel(channel_id: UUID):
        with jobs_db._conn() as con:
            con.execute("DELETE FROM source_channel_state WHERE channel_id=?", (str(channel_id),))
            con.execute("DELETE FROM source_video_stats WHERE video_id IN "
                        "(SELECT video_id FROM source_videos WHERE channel_id=?)", (str(channel_id),))
            con.execute("DELETE FROM source_videos WHERE channel_id=?", (str(channel_id),))
            result = con.execute("DELETE FROM source_channels WHERE id=?", (str(channel_id),))
        if not result.rowcount:
            raise HTTPException(404, "Channel not found.")
        return Response(status_code=204)

    class SourceTopics(BaseModel):
        topics: str

    @app.get("/api/source-topics")
    def source_topics():
        return {"topics": jobs_db.get_setting("source_topics") or ""}

    @app.put("/api/source-topics")
    def update_source_topics(body: SourceTopics):
        topics = body.topics.strip()
        if len(topics) > 500:
            raise HTTPException(400, "Topics must be under 500 characters.")
        jobs_db.save_settings({"source_topics": topics})
        return {"topics": topics}

    class SourceAutomation(BaseModel):
        enabled: bool

    @app.get("/api/source-automation")
    def source_automation_status():
        from source_automation import enabled
        return {"enabled": enabled()}

    @app.put("/api/source-automation")
    def update_source_automation(body: SourceAutomation):
        jobs_db.save_settings({"source_auto_enabled": "1" if body.enabled else "0"})
        return {"enabled": body.enabled}

    @app.get("/api/source-videos")
    def list_source_videos():
        from source_discovery import title_matches_topics
        with jobs_db._conn() as con:
            rows = con.execute(
                "SELECT v.video_id, v.title, v.published_at, c.url AS channel_url, s.views, s.likes, "
                "a.state AS auto_state, a.message AS auto_message, a.job_id AS auto_job_id "
                "FROM source_videos v JOIN source_channels c ON c.id=v.channel_id "
                "LEFT JOIN source_video_stats s ON s.video_id=v.video_id "
                "LEFT JOIN source_auto_jobs a ON a.video_id=v.video_id "
                "ORDER BY v.published_at DESC LIMIT 100"
            ).fetchall()
        topics = jobs_db.get_setting("source_topics") or ""
        videos = [dict(row) for row in rows]
        for video in videos:
            video["topic_match"] = bool(topics and title_matches_topics(video["title"], topics))
            video["views_per_day"] = None
            if video["views"] is not None and video["published_at"]:
                try:
                    published = datetime.fromisoformat(
                        video["published_at"].replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - published).total_seconds()
                    video["views_per_day"] = round(video["views"] / max(age / 86400, 1))
                except (ValueError, TypeError):
                    pass
        videos.sort(key=lambda video: (video["topic_match"], video["views_per_day"] or -1,
                                       video["published_at"] or ""), reverse=True)
        return {"videos": videos,
                "statistics_configured": bool(os.environ.get("YOUTUBE_DATA_API_KEY", "").strip())}

    @app.get("/api/library")
    def list_clips():
        return library.clips()

    @app.api_route("/api/library/{job_id}/{index}", methods=["GET", "DELETE"])
    async def clip(request: Request, job_id: UUID, index: int):
        directory = library.root / str(job_id)
        path = directory / f"{index}.mp4"
        manifest = directory / "index.json"
        try:
            entries = json.loads(manifest.read_text())
            entry = next(item for item in entries if item.get("index") == index)
        except (FileNotFoundError, ValueError, StopIteration):
            raise HTTPException(404, "Clip no longer in library.")
        receipts_path = directory / ".drive-receipts.json"
        try:
            receipts = json.loads(receipts_path.read_text())
        except (FileNotFoundError, ValueError):
            receipts = {}
        receipt = receipts.get(f"{job_id}-{index}") or {}
        file_id = receipt.get("id")
        if request.method == "DELETE":
            # Removing from the app library leaves any backup in Drive.
            updated = [item for item in entries if item.get("index") != index]
            with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as temporary:
                json.dump(updated, temporary)
                temp_path = temporary.name
            os.replace(temp_path, manifest)
            path.unlink(missing_ok=True)
            return Response(status_code=204)
        if path.is_file():
            return FileResponse(path, filename=entry["filename"], media_type="video/mp4")
        if not file_id or not re.fullmatch(r"[A-Za-z0-9_-]+", file_id):
            raise HTTPException(404, "Clip no longer in library.")
        connection_path = library.root / ".drive-connection.json"
        try:
            connection = json.loads(connection_path.read_text())
        except (FileNotFoundError, ValueError):
            raise HTTPException(409, "Reconnect Google Drive to download this clip.")
        from drive_connection import refresh_access_token
        token = await refresh_access_token(connection)
        client = httpx.AsyncClient(timeout=httpx.Timeout(60, connect=20))
        headers = {"Authorization": "Bearer " + token}
        if request.headers.get("range"):
            headers["Range"] = request.headers["range"]
        try:
            upstream = await client.send(client.build_request(
                "GET", f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"alt": "media", "supportsAllDrives": "true"}, headers=headers), stream=True)
        except httpx.HTTPError as exc:
            await client.aclose()
            raise HTTPException(502, "Could not download the clip from Google Drive.") from exc
        if upstream.status_code not in (200, 206):
            await upstream.aclose()
            await client.aclose()
            raise HTTPException(502, "Could not download the clip from Google Drive.")
        async def stream():
            try:
                async for chunk in upstream.aiter_bytes():
                    yield chunk
            finally:
                await upstream.aclose()
                await client.aclose()
        response_headers = {
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(entry["filename"], safe=""),
            "Accept-Ranges": upstream.headers.get("accept-ranges", "bytes"),
        }
        for header in ("content-length", "content-range"):
            if header in upstream.headers:
                response_headers[header] = upstream.headers[header]
        return StreamingResponse(stream(), status_code=upstream.status_code,
                                 media_type="video/mp4", headers=response_headers)
