"""Project-scoped Business Login for Instagram."""
import json
import asyncio
import hashlib
import os
import secrets
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

import jobs_db


def credentials():
    return os.getenv('INSTAGRAM_APP_ID', '').strip(), os.getenv('INSTAGRAM_APP_SECRET', '').strip()


def redirect_uri():
    return os.getenv('INSTAGRAM_OAUTH_REDIRECT_URI', 'https://openshorts-dev.duckdns.org/api/factory/instagram/callback').strip()


def public_site():
    from urllib.parse import urlsplit
    value = os.getenv('FACTORY_PUBLIC_SITE_URL', 'https://openshorts-dev.duckdns.org').strip().rstrip('/')
    parts = urlsplit(value)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.path or parts.query or parts.fragment:
        raise ValueError('An HTTPS public site URL is required')
    return value


def read_connection(root, channel_id):
    path = Path(root) / '.instagram-connections' / f'{UUID(str(channel_id))}.json'
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}


def write_connection(root, channel_id, value):
    directory = Path(root) / '.instagram-connections'
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=directory, mode='w', delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle)
    try:
        os.chmod(temporary, 0o600)
        os.replace(temporary, directory / f'{UUID(str(channel_id))}.json')
    finally:
        temporary.unlink(missing_ok=True)


def install(app, library):
    pending = {}

    @app.get('/api/factory/channels/{channel_id}/instagram/connect')
    def connect(channel_id: UUID, request: Request):
        client, secret = credentials()
        if not client or not secret:
            raise HTTPException(503, 'Instagram app credentials are not configured on the server.')
        with jobs_db._conn() as con:
            if not con.execute('SELECT 1 FROM factory_channels WHERE id=?', (str(channel_id),)).fetchone():
                raise HTTPException(404, 'Project not found.')
        now = time.monotonic()
        for old in list(pending):
            if now - pending[old][0] > 600:
                del pending[old]
        state = secrets.token_urlsafe(32)
        pending[state] = (now, request.cookies.get('openshorts_owner'), str(channel_id))
        params = {'client_id': client, 'redirect_uri': redirect_uri(), 'response_type': 'code', 'state': state,
                  'scope': 'instagram_business_basic,instagram_business_content_publish'}
        return RedirectResponse('https://www.instagram.com/oauth/authorize?' + urlencode(params))

    @app.get('/api/factory/instagram/callback')
    async def callback(request: Request, state: str = '', code: str = ''):
        entry = pending.pop(state, None)
        if not entry or time.monotonic() - entry[0] > 600 or entry[1] != request.cookies.get('openshorts_owner'):
            raise HTTPException(400, 'Authorization expired. Sign in and try again.')
        if not code:
            raise HTTPException(400, 'Instagram authorization was cancelled.')
        client, secret = credentials()
        try:
            async with httpx.AsyncClient(timeout=20) as http:
                form = {'client_id': client, 'client_secret': secret, 'grant_type': 'authorization_code',
                        'redirect_uri': redirect_uri(), 'code': code}
                short = await http.post('https://api.instagram.com/oauth/access_token', files={key: (None, value) for key, value in form.items()})
                short.raise_for_status()
                data = short.json()
                # Meta has returned both a single object and a data array across API versions.
                short_data = data['data'][0] if isinstance(data.get('data'), list) else data
                long = await http.get('https://graph.instagram.com/access_token', params={'grant_type': 'ig_exchange_token',
                    'client_secret': secret, 'access_token': short_data['access_token']})
                long.raise_for_status()
                token = long.json()
                profile = await http.get('https://graph.instagram.com/me', params={'fields': 'user_id,username,account_type'},
                    headers={'Authorization': 'Bearer ' + token['access_token']})
                profile.raise_for_status()
                user = profile.json()
                if user.get('account_type') not in {'BUSINESS', 'MEDIA_CREATOR'} or not user.get('user_id'):
                    raise ValueError('Instagram professional account required')
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise HTTPException(502, 'Could not connect the Instagram professional account. Try again.') from exc
        with jobs_db._conn() as con:
            if not con.execute('SELECT 1 FROM factory_channels WHERE id=?', (entry[2],)).fetchone():
                raise HTTPException(404, 'Project no longer exists.')
        write_connection(library.root, entry[2], {'access_token': token['access_token'], 'user_id': str(user['user_id']),
                         'username': user.get('username', ''), 'issued_at': time.time(), 'expires_at': time.time() + int(token['expires_in'])})
        return RedirectResponse('/#app?instagram=connected', status_code=303)

    @app.delete('/api/factory/channels/{channel_id}/instagram/connection')
    def disconnect(channel_id: UUID):
        (Path(library.root) / '.instagram-connections' / f'{channel_id}.json').unlink(missing_ok=True)
        return {'connected': False}

    @app.get('/api/factory/media/{token}', include_in_schema=False)
    def media(token: str):
        # This URL is a temporary capability used by Meta to fetch one selected video.
        if len(token) != 43 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in token):
            raise HTTPException(404, 'Not found.')
        digest = hashlib.sha256(token.encode()).hexdigest()
        with jobs_db._conn() as con:
            row = con.execute('SELECT idea_id,revision FROM factory_media_grants WHERE token_hash=? AND expires_at>?',
                              (digest, time.time())).fetchone()
        path = Path(library.root) / 'factory' / str(UUID(row['idea_id'])) / f"{row['revision']}.mp4" if row else None
        if not path or not path.is_file():
            raise HTTPException(404, 'Not found.')
        return FileResponse(path, media_type='video/mp4', headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})

    @app.post('/api/factory/ideas/{idea_id}/instagram/publish')
    async def publish(idea_id: UUID, expected_revision: int | None = None):
        with jobs_db._conn() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute("SELECT i.channel_id,i.idea,s.revision FROM factory_ideas i "
                "JOIN factory_scripts s ON s.idea_id=i.id JOIN factory_renders r ON r.idea_id=i.id AND r.revision=s.revision "
                "JOIN factory_review_queue q ON q.idea_id=i.id AND q.revision=s.revision "
                "WHERE i.id=? AND i.status='approved' AND s.status='approved' AND q.status='approved'", (str(idea_id),)).fetchone()
            if not row:
                raise HTTPException(400, 'Approve the current video before publishing.')
            if expected_revision is not None:
                mode = con.execute('SELECT publishing_mode FROM factory_project_settings WHERE channel_id=?', (row['channel_id'],)).fetchone()
                if row['revision'] != expected_revision or not mode or mode['publishing_mode'] != 'automatic':
                    raise HTTPException(409, 'The video or automatic publishing setting changed.')
            if con.execute("SELECT 1 FROM factory_render_jobs WHERE idea_id=? AND status='processing'", (str(idea_id),)).fetchone():
                raise HTTPException(409, 'Wait for rendering to finish before publishing.')
            connection = read_connection(library.root, row['channel_id'])
            if not connection.get('access_token') or not connection.get('user_id') or connection.get('expires_at', 0) <= time.time():
                raise HTTPException(409, 'Connect the project’s Instagram account first.')
            path = Path(library.root) / 'factory' / str(idea_id) / f"{row['revision']}.mp4"
            if not path.is_file() or not path.stat().st_size:
                raise HTTPException(409, 'The video file is unavailable. Render it again first.')
            previous = con.execute("SELECT status FROM factory_publications WHERE idea_id=? AND revision=? AND platform='instagram'",
                                   (str(idea_id), row['revision'])).fetchone()
            if previous and previous['status'] != 'failed':
                raise HTTPException(409, 'This video is already published or its upload needs checking on Instagram.')
            con.execute("INSERT INTO factory_publications VALUES (?,?, 'instagram','preparing',NULL,NULL,?) "
                        "ON CONFLICT(idea_id,revision,platform) DO UPDATE SET status='preparing',error=NULL,updated_at=excluded.updated_at",
                        (str(idea_id), row['revision'], jobs_db._utcnow()))
        revision = row['revision']
        publishing_started = False
        token_value = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token_value.encode()).hexdigest()
        try:
            base = public_site()
            async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=15), follow_redirects=False) as http:
                if connection['expires_at'] - time.time() < 14 * 86400 and time.time() - connection.get('issued_at', 0) >= 86400:
                    refreshed = await http.get('https://graph.instagram.com/refresh_access_token',
                        params={'grant_type': 'ig_refresh_token', 'access_token': connection['access_token']})
                    refreshed.raise_for_status()
                    fresh = refreshed.json()
                    connection.update({'access_token': fresh['access_token'], 'issued_at': time.time(),
                                       'expires_at': time.time() + int(fresh['expires_in'])})
                    write_connection(library.root, row['channel_id'], connection)
                with jobs_db._conn() as con:
                    con.execute('DELETE FROM factory_media_grants WHERE expires_at<?', (time.time(),))
                    con.execute('INSERT INTO factory_media_grants VALUES (?,?,?,?)', (digest, str(idea_id), revision, time.time() + 1800))
                endpoint = 'https://graph.instagram.com/v27.0/' + connection['user_id']
                headers = {'Authorization': 'Bearer ' + connection['access_token']}
                created = await http.post(endpoint + '/media', headers=headers,
                    json={'media_type': 'REELS', 'video_url': base + '/api/factory/media/' + token_value,
                          'caption': row['idea'][:2000] + ' #shorts', 'is_ai_generated': True})
                created.raise_for_status()
                container_id = str(created.json()['id'])
                if not container_id.isdigit():
                    raise ValueError('Invalid Instagram container')
                for _ in range(30):
                    status = await http.get('https://graph.instagram.com/v27.0/' + container_id,
                                            params={'fields': 'status_code'}, headers=headers)
                    status.raise_for_status()
                    state = status.json().get('status_code')
                    if state == 'FINISHED':
                        break
                    if state in {'ERROR', 'EXPIRED'}:
                        raise ValueError('Instagram video processing failed')
                    await asyncio.sleep(4)
                else:
                    raise ValueError('Instagram video processing timed out')
                with jobs_db._conn() as con:
                    con.execute("UPDATE factory_publications SET status='uploading',remote_id=?,updated_at=? WHERE idea_id=? AND revision=? AND platform='instagram'",
                                (container_id, jobs_db._utcnow(), str(idea_id), revision))
                publishing_started = True
                published = await http.post(endpoint + '/media_publish', headers=headers, json={'creation_id': container_id})
                published.raise_for_status()
                remote_id = str(published.json()['id'])
                if not remote_id.isdigit():
                    raise ValueError('Missing Instagram media id')
            with jobs_db._conn() as con:
                con.execute("UPDATE factory_publications SET status='published',remote_id=?,error=NULL,updated_at=? "
                            "WHERE idea_id=? AND revision=? AND platform='instagram'", (remote_id, jobs_db._utcnow(), str(idea_id), revision))
                con.execute("UPDATE factory_publish_queue SET status='published',error=NULL,updated_at=? "
                            "WHERE idea_id=? AND revision=? AND platform='instagram' AND status IN ('pending','processing')", (jobs_db._utcnow(), str(idea_id), revision))
            return {'status': 'published', 'media_id': remote_id}
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as exc:
            state = 'uncertain' if publishing_started else 'failed'
            with jobs_db._conn() as con:
                con.execute("UPDATE factory_publications SET status=?,error=?,updated_at=? WHERE idea_id=? AND revision=? AND platform='instagram'",
                            (state, 'Check Instagram before trying again.' if publishing_started else 'Could not prepare Instagram upload.',
                             jobs_db._utcnow(), str(idea_id), revision))
            raise HTTPException(502, 'Publishing outcome is uncertain. Check Instagram.' if publishing_started else 'Could not prepare Instagram upload.') from exc
        finally:
            with jobs_db._conn() as con:
                con.execute('DELETE FROM factory_media_grants WHERE token_hash=?', (digest,))

    app.state.factory_instagram_publish = publish
