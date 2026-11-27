"""Private single-owner session and persistent finished-clip library."""
import hmac
import os
import json
import secrets
import shutil
import tempfile
import time
from pathlib import Path
from uuid import UUID, uuid4
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
                                or clip.get("title") or name, "filename": name})
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
        if request.url.path not in public:
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

    @app.get("/api/source-videos")
    def list_source_videos():
        from source_discovery import title_matches_topics
        with jobs_db._conn() as con:
            rows = con.execute(
                "SELECT v.video_id, v.title, v.published_at, c.url AS channel_url, s.views, s.likes "
                "FROM source_videos v JOIN source_channels c ON c.id=v.channel_id "
                "LEFT JOIN source_video_stats s ON s.video_id=v.video_id "
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
