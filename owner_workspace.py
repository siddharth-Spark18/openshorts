"""Private single-owner session and persistent finished-clip library."""
import hmac
import os
import json
import secrets
import shutil
import tempfile
import time
from pathlib import Path
from uuid import UUID

from fastapi import File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

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
            for entry in json.loads(manifest.read_text()):
                path = manifest.parent / f"{entry['index']}.mp4"
                if path.is_file():
                    rows.append({**entry, "job_id": manifest.parent.name})
        return rows


def install(app, password, library):
    sessions = {}

    @app.middleware("http")
    async def require_owner(request: Request, call_next):
        public = {"/owner/login", "/health/ready", "/health/live"}
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
                            secure=request.url.scheme == "https", samesite="strict")
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

    @app.get("/api/library")
    def list_clips():
        return library.clips()

    @app.api_route("/api/library/{job_id}/{index}", methods=["GET", "DELETE"])
    async def clip(request: Request, job_id: UUID, index: int):
        directory = library.root / str(job_id)
        path = directory / f"{index}.mp4"
        if not path.is_file():
            raise HTTPException(404, "Clip no longer in library.")
        if request.method == "DELETE":
            path.unlink(missing_ok=True)
            return Response(status_code=204)
        entries = json.loads((directory / "index.json").read_text())
        return FileResponse(path, filename=entries[index]["filename"], media_type="video/mp4")
