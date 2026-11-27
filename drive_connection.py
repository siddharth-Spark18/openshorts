"""Single-owner Google Drive authorization and selected-folder connection."""
import hashlib
import base64
import json
import os
import secrets
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

SCOPE = "https://www.googleapis.com/auth/drive.file"
CALLBACK = "https://openshorts-dev.duckdns.org/api/drive/callback"
TOKEN_URL = "https://oauth2.googleapis.com/token"


async def refresh_access_token(data):
    client = os.getenv("DRIVE_CLIENT_ID", "").strip()
    secret = os.getenv("DRIVE_CLIENT_SECRET", "").strip()
    if not data.get("refresh_token") or not client or not secret:
        raise HTTPException(409, "Connect Google Drive first.")
    async with httpx.AsyncClient(timeout=20) as http:
        response = await http.post(TOKEN_URL, data={
            "client_id": client, "client_secret": secret,
            "refresh_token": data["refresh_token"], "grant_type": "refresh_token",
        })
    if response.status_code != 200:
        raise HTTPException(502, "Google authorization expired. Connect Google Drive again.")
    return response.json()["access_token"]


class FolderSelection(BaseModel):
    id: str


def install(app, library):
    path = library.root / ".drive-connection.json"
    pending = {}

    def config():
        client = os.getenv("DRIVE_CLIENT_ID", "").strip()
        secret = os.getenv("DRIVE_CLIENT_SECRET", "").strip()
        picker = os.getenv("DRIVE_PICKER_API_KEY", "").strip()
        return client, secret, picker

    def read():
        try:
            return json.loads(path.read_text())
        except FileNotFoundError:
            return {}

    def write(data):
        with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", delete=False) as file:
            temporary = Path(file.name)
            json.dump(data, file)
        try:
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


    @app.get("/api/drive/status")
    def status():
        client, secret, picker = config()
        data = read()
        return {"available": bool(client and secret and picker), "connected": bool(data.get("refresh_token")),
                "folder_name": data.get("folder_name"), "folder_id": data.get("folder_id"),
                "archive_status": getattr(library, "drive_status", "pending")}

    @app.get("/api/drive/connect")
    def connect(request: Request):
        client, secret, picker = config()
        if not all((client, secret, picker)):
            raise HTTPException(503, "Google Drive credentials are not configured on the server.")
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        pending[state] = (time.monotonic(), request.cookies.get("openshorts_owner"), verifier)
        params = {"client_id": client, "redirect_uri": CALLBACK, "response_type": "code",
                  "scope": SCOPE, "access_type": "offline", "prompt": "consent",
                  "state": state, "code_challenge": challenge, "code_challenge_method": "S256"}
        return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))

    @app.get("/api/drive/callback")
    async def callback(request: Request, state: str = "", code: str = ""):
        record = pending.pop(state, None)
        if not record or time.monotonic() - record[0] > 600 or record[1] != request.cookies.get("openshorts_owner"):
            raise HTTPException(400, "Authorization expired. Sign in and try again.")
        if not code:
            raise HTTPException(400, "Google authorization was cancelled.")
        client, secret, _ = config()
        async with httpx.AsyncClient(timeout=20) as http:
            response = await http.post(TOKEN_URL, data={
                "code": code, "client_id": client, "client_secret": secret,
                "redirect_uri": CALLBACK, "grant_type": "authorization_code", "code_verifier": record[2],
            })
        if response.status_code != 200 or not response.json().get("refresh_token"):
            raise HTTPException(502, "Google did not provide offline access. Connect again.")
        write({"refresh_token": response.json()["refresh_token"]})
        return RedirectResponse("/#app?drive=connected", status_code=303)

    @app.get("/api/drive/picker")
    async def picker():
        client, _, api_key = config()
        return {"token": await refresh_access_token(read()), "api_key": api_key, "app_id": client.split("-")[0]}

    @app.put("/api/drive/folder")
    async def select_folder(selection: FolderSelection):
        if not selection.id or len(selection.id) > 200:
            raise HTTPException(400, "Invalid folder.")
        data = read()
        token = await refresh_access_token(data)
        async with httpx.AsyncClient(timeout=20) as http:
            response = await http.get(
                "https://www.googleapis.com/drive/v3/files/" + selection.id,
                params={"fields": "id,name,mimeType,capabilities(canAddChildren)", "supportsAllDrives": "true"},
                headers={"Authorization": "Bearer " + token},
            )
        if response.status_code != 200:
            raise HTTPException(400, "Google could not access the selected folder.")
        folder = response.json()
        if folder.get("mimeType") != "application/vnd.google-apps.folder" or not folder.get("capabilities", {}).get("canAddChildren"):
            raise HTTPException(400, "Choose a folder where you can add files.")
        data.update({"folder_id": folder["id"], "folder_name": folder["name"]})
        write(data)
        return {"folder_name": folder["name"]}

    @app.delete("/api/drive/connection")
    def disconnect():
        path.unlink(missing_ok=True)
        return {"ok": True}
