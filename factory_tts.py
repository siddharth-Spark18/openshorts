"""Google Cloud speech with a conservative, shared monthly character cap."""
import base64
import json
import os
from datetime import datetime, timezone

import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import httpx

import jobs_db

MONTHLY_LIMIT = 750_000
VOICES = {'en-US-Neural2-F', 'en-US-Neural2-D', 'en-US-Neural2-C', 'en-US-Neural2-J'}


class SpeechError(Exception):
    pass


def reserve(characters):
    month = datetime.now(timezone.utc).strftime('%Y-%m')
    with jobs_db._conn() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT characters FROM factory_tts_usage WHERE month=?', (month,)).fetchone()
        used = row['characters'] if row else 0
        if used + characters > MONTHLY_LIMIT:
            raise SpeechError('The monthly Google voice limit has been reached.')
        con.execute('INSERT INTO factory_tts_usage VALUES (?,?) ON CONFLICT(month) DO UPDATE SET characters=excluded.characters',
                    (month, used + characters))


def synthesize(text, path, voice):
    if voice not in VOICES:
        raise SpeechError('Invalid Google voice.')
    try:
        info = os.environ.get('GOOGLE_TTS_CREDENTIALS_JSON', '').strip()
        scopes = ['https://www.googleapis.com/auth/cloud-platform']
        if info:
            creds = service_account.Credentials.from_service_account_info(json.loads(info), scopes=scopes)
        else:
            creds, _ = google.auth.default(scopes=scopes)
        creds.refresh(Request())
    except Exception as exc:
        raise SpeechError('Google voice credentials are missing or invalid.') from exc
    reserve(len(text))
    try:
        response = httpx.post('https://texttospeech.googleapis.com/v1/text:synthesize', timeout=45,
            headers={'Authorization': 'Bearer ' + creds.token},
            json={'input': {'text': text}, 'voice': {'languageCode': 'en-US', 'name': voice},
                  'audioConfig': {'audioEncoding': 'LINEAR16', 'speakingRate': 1.0}})
        response.raise_for_status()
        audio = base64.b64decode(response.json()['audioContent'], validate=True)
        if not audio:
            raise ValueError('Empty audio')
        path.write_bytes(audio)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise SpeechError('Google voice generation failed. Check the API and credentials.') from exc
