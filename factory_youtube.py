"""Project-scoped YouTube authorization; refresh tokens never leave the server."""
import base64
import hashlib
import json
import os
import secrets
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

import jobs_db

SCOPES = 'https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
CHANNELS_URL = 'https://www.googleapis.com/youtube/v3/channels'
UPLOAD_URL = 'https://www.googleapis.com/upload/youtube/v3/videos'


def credentials():
    return (os.getenv('YOUTUBE_CLIENT_ID', '').strip() or os.getenv('DRIVE_CLIENT_ID', '').strip(),
            os.getenv('YOUTUBE_CLIENT_SECRET', '').strip() or os.getenv('DRIVE_CLIENT_SECRET', '').strip())


def redirect_uri():
    return os.getenv('YOUTUBE_OAUTH_REDIRECT_URI', 'https://openshorts-dev.duckdns.org/api/factory/youtube/callback').strip()


def read_connection(root, channel_id):
    path = Path(root) / '.youtube-connections' / f'{UUID(str(channel_id))}.json'
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}


def write_connection(root, channel_id, value):
    directory = Path(root) / '.youtube-connections'
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / f'{UUID(str(channel_id))}.json'
    with tempfile.NamedTemporaryFile(dir=directory, mode='w', delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle)
    try:
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def install(app, library):
    pending = {}

    @app.get('/api/factory/channels/{channel_id}/youtube/connect')
    def connect(channel_id: UUID, request: Request):
        client, secret = credentials()
        if not client or not secret:
            raise HTTPException(503, 'YouTube credentials are not configured on the server.')
        with jobs_db._conn() as con:
            if not con.execute('SELECT 1 FROM factory_channels WHERE id=?', (str(channel_id),)).fetchone():
                raise HTTPException(404, 'Project not found.')
        now = time.monotonic()
        for old in list(pending):
            if now - pending[old][0] > 600:
                del pending[old]
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        pending[state] = (now, request.cookies.get('openshorts_owner'), verifier, str(channel_id))
        query = urlencode({'client_id': client, 'redirect_uri': redirect_uri(), 'response_type': 'code',
                           'scope': SCOPES, 'access_type': 'offline', 'prompt': 'consent', 'state': state,
                           'code_challenge': challenge, 'code_challenge_method': 'S256'})
        return RedirectResponse('https://accounts.google.com/o/oauth2/v2/auth?' + query)

    @app.get('/api/factory/youtube/callback')
    async def callback(request: Request, state: str = '', code: str = ''):
        entry = pending.pop(state, None)
        if not entry or time.monotonic() - entry[0] > 600 or entry[1] != request.cookies.get('openshorts_owner'):
            raise HTTPException(400, 'Authorization expired. Sign in and try again.')
        if not code:
            raise HTTPException(400, 'YouTube authorization was cancelled.')
        client, secret = credentials()
        try:
            async with httpx.AsyncClient(timeout=20) as http:
                token_response = await http.post(TOKEN_URL, data={'code': code, 'client_id': client,
                    'client_secret': secret, 'redirect_uri': redirect_uri(), 'grant_type': 'authorization_code',
                    'code_verifier': entry[2]})
                token_response.raise_for_status()
                token = token_response.json()
                if not token.get('refresh_token') or not token.get('access_token'):
                    raise ValueError('Missing offline authorization')
                channels_response = await http.get(CHANNELS_URL, params={'part': 'snippet', 'mine': 'true'},
                    headers={'Authorization': 'Bearer ' + token['access_token']})
                channels_response.raise_for_status()
                channels = channels_response.json().get('items', [])
                if len(channels) != 1 or not channels[0].get('id') or not channels[0].get('snippet', {}).get('title'):
                    raise ValueError('Could not identify exactly one YouTube channel')
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise HTTPException(502, 'Could not connect the selected YouTube channel. Try again.') from exc
        with jobs_db._conn() as con:
            if not con.execute('SELECT 1 FROM factory_channels WHERE id=?', (entry[3],)).fetchone():
                raise HTTPException(404, 'Project no longer exists.')
        write_connection(library.root, entry[3], {'refresh_token': token['refresh_token'],
                         'channel_id': channels[0]['id'], 'channel_title': channels[0]['snippet']['title']})
        return RedirectResponse('/#app?youtube=connected', status_code=303)

    @app.delete('/api/factory/channels/{channel_id}/youtube/connection')
    def disconnect(channel_id: UUID):
        (Path(library.root) / '.youtube-connections' / f'{channel_id}.json').unlink(missing_ok=True)
        return {'connected': False}

    @app.post('/api/factory/ideas/{idea_id}/youtube/publish')
    async def publish(idea_id: UUID, expected_revision: int | None = None):
        with jobs_db._conn() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute("SELECT i.channel_id,i.idea,s.revision FROM factory_ideas i "
                "JOIN factory_scripts s ON s.idea_id=i.id JOIN factory_renders r ON r.idea_id=i.id AND r.revision=s.revision "
                "JOIN factory_review_queue q ON q.idea_id=i.id AND q.revision=s.revision "
                "WHERE i.id=? AND i.status='approved' AND s.status='approved' AND q.status='approved'", (str(idea_id),)).fetchone()
            if not row:
                raise HTTPException(400, 'Approve the current video before publishing.')
            if con.execute("SELECT 1 FROM factory_render_jobs WHERE idea_id=? AND status='processing'", (str(idea_id),)).fetchone():
                raise HTTPException(409, 'Wait for rendering to finish before publishing.')
            if expected_revision is not None:
                mode = con.execute('SELECT publishing_mode FROM factory_project_settings WHERE channel_id=?', (row['channel_id'],)).fetchone()
                if row['revision'] != expected_revision or not mode or mode['publishing_mode'] != 'automatic':
                    raise HTTPException(409, 'The video or automatic publishing setting changed.')
            connection = read_connection(library.root, row['channel_id'])
            if not connection.get('refresh_token') or not connection.get('channel_id'):
                raise HTTPException(409, 'Connect the project’s YouTube channel first.')
            path = Path(library.root) / 'factory' / str(idea_id) / f"{row['revision']}.mp4"
            if not path.is_file() or not path.stat().st_size:
                raise HTTPException(409, 'The video file is unavailable. Render it again first.')
            previous = con.execute("SELECT status FROM factory_publications WHERE idea_id=? AND revision=? AND platform='youtube'",
                                   (str(idea_id), row['revision'])).fetchone()
            if previous and previous['status'] != 'failed':
                raise HTTPException(409, 'This video is already published or its upload needs checking in YouTube Studio.')
            con.execute("INSERT INTO factory_publications VALUES (?,?, 'youtube','preparing',NULL,NULL,?) "
                        "ON CONFLICT(idea_id,revision,platform) DO UPDATE SET status='preparing',error=NULL,updated_at=excluded.updated_at",
                        (str(idea_id), row['revision'], jobs_db._utcnow()))
        revision = row['revision']
        upload_started = False
        try:
            client_id, client_secret = credentials()
            if not client_id or not client_secret:
                raise ValueError('YouTube credentials are not configured')
            async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=20), follow_redirects=False) as http:
                refresh = await http.post(TOKEN_URL, data={'client_id': client_id, 'client_secret': client_secret,
                    'refresh_token': connection['refresh_token'], 'grant_type': 'refresh_token'})
                refresh.raise_for_status()
                access_token = refresh.json()['access_token']
                start = await http.post(UPLOAD_URL, params={'uploadType': 'resumable', 'part': 'snippet,status'},
                    headers={'Authorization': 'Bearer ' + access_token, 'X-Upload-Content-Type': 'video/mp4',
                             'X-Upload-Content-Length': str(path.stat().st_size)},
                    json={'snippet': {'title': row['idea'][:90].strip() + ' #shorts',
                                      'description': 'An original workplace skit. #shorts'},
                          'status': {'privacyStatus': 'public', 'selfDeclaredMadeForKids': False}})
                start.raise_for_status()
                location = start.headers['location']
                parsed = urlsplit(location)
                if parsed.scheme != 'https' or parsed.hostname != 'www.googleapis.com':
                    raise ValueError('Invalid upload destination')
                with jobs_db._conn() as con:
                    con.execute("UPDATE factory_publications SET status='uploading',updated_at=? WHERE idea_id=? AND revision=? AND platform='youtube'",
                                (jobs_db._utcnow(), str(idea_id), revision))
                upload_started = True
                async def chunks():
                    with path.open('rb') as video:
                        while block := video.read(1024 * 1024):
                            yield block
                uploaded = await http.put(location, content=chunks(), headers={'Content-Type': 'video/mp4',
                                          'Content-Length': str(path.stat().st_size)})
                uploaded.raise_for_status()
                remote_id = uploaded.json()['id']
                if not isinstance(remote_id, str) or not remote_id:
                    raise ValueError('Missing video id')
            with jobs_db._conn() as con:
                con.execute("UPDATE factory_publications SET status='published',remote_id=?,error=NULL,updated_at=? "
                            "WHERE idea_id=? AND revision=? AND platform='youtube'", (remote_id, jobs_db._utcnow(), str(idea_id), revision))
                con.execute("UPDATE factory_publish_queue SET status='published',error=NULL,updated_at=? "
                            "WHERE idea_id=? AND revision=? AND platform='youtube' AND status IN ('pending','processing')", (jobs_db._utcnow(), str(idea_id), revision))
            return {'status': 'published', 'video_id': remote_id}
        except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
            status = 'uncertain' if upload_started else 'failed'
            with jobs_db._conn() as con:
                con.execute("UPDATE factory_publications SET status=?,error=?,updated_at=? WHERE idea_id=? AND revision=? AND platform='youtube'",
                            (status, 'Check YouTube Studio before trying again.' if upload_started else 'Could not start upload.',
                             jobs_db._utcnow(), str(idea_id), revision))
            raise HTTPException(502, 'Upload outcome is uncertain. Check YouTube Studio.' if upload_started else 'Could not start YouTube upload.') from exc

    app.state.factory_youtube_publish = publish
