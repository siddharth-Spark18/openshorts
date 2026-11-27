"""Upload saved clips to the selected Google Drive folder.

Local library files remain available until remote storage and recovery have
been verified. The appProperties key makes retries safe after a lost response.
"""
import hashlib
import json
import os
from pathlib import Path

import httpx

from drive_connection import TOKEN_URL


class DriveArchiveError(Exception):
    pass


class DriveArchive:
    def __init__(self, root):
        self.root = Path(root)

    def connection(self):
        try:
            data = json.loads((self.root / ".drive-connection.json").read_text())
        except (FileNotFoundError, ValueError):
            return None
        return data if data.get("refresh_token") and data.get("folder_id") else None

    def sync(self):
        connection = self.connection()
        if not connection:
            return False
        client_id = os.getenv("DRIVE_CLIENT_ID", "")
        client_secret = os.getenv("DRIVE_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            raise DriveArchiveError("Google Drive credentials are missing.")
        with httpx.Client(timeout=httpx.Timeout(60, connect=20)) as http:
            response = http.post(TOKEN_URL, data={
                "client_id": client_id, "client_secret": client_secret,
                "refresh_token": connection["refresh_token"], "grant_type": "refresh_token",
            })
            if not response.is_success:
                raise DriveArchiveError("Google Drive authorization failed. Reconnect your account.")
            headers = {"Authorization": "Bearer " + response.json()["access_token"]}
            for manifest in self.root.glob("*/index.json"):
                self._sync_job(http, headers, connection["folder_id"], manifest)
        return True

    def _sync_job(self, http, headers, folder_id, manifest):
        # Keep a separate receipt so existing library indexes and deletions
        # retain their established meaning.
        receipts_path = manifest.parent / ".drive-receipts.json"
        try:
            receipts = json.loads(receipts_path.read_text())
        except FileNotFoundError:
            receipts = {}
        for entry in json.loads(manifest.read_text()):
            index = entry["index"]
            video = manifest.parent / f"{index}.mp4"
            if not video.is_file():
                continue
            key = f"{manifest.parent.name}-{index}"
            if receipts.get(key, {}).get("folder_id") == folder_id:
                continue
            if not all(c.isalnum() or c in "-_" for c in folder_id):
                raise DriveArchiveError("Invalid Google Drive folder ID.")
            query = ("trashed = false and '%s' in parents and appProperties has "
                     "{ key='openshorts_clip' and value='%s' }" % (folder_id, key))
            digest = hashlib.md5()
            with video.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            checksum = digest.hexdigest()
            response = http.get("https://www.googleapis.com/drive/v3/files",
                                headers=headers, params={"q": query, "fields": "files(id,size,md5Checksum)", "pageSize": 100,
                                        "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"})
            response.raise_for_status()
            matches = [item for item in response.json().get("files", [])
                       if item.get("md5Checksum") == checksum
                       and int(item.get("size", -1)) == video.stat().st_size]
            if matches:
                file_id = matches[0]["id"]
            else:
                response = http.post(
                    "https://www.googleapis.com/upload/drive/v3/files",
                    headers={**headers, "X-Upload-Content-Type": "video/mp4",
                             "X-Upload-Content-Length": str(video.stat().st_size)},
                    params={"uploadType": "resumable", "fields": "id", "supportsAllDrives": "true"},
                    json={"name": entry["filename"], "parents": [folder_id],
                          "appProperties": {"openshorts_clip": key}},
                )
                response.raise_for_status()
                upload_url = response.headers["location"]
                size = video.stat().st_size
                offset = 0
                with video.open("rb") as source:
                    while offset < size:
                        source.seek(offset)
                        chunk = source.read(min(8 * 1024 * 1024, size - offset))
                        end = offset + len(chunk) - 1
                        result = http.put(upload_url, content=chunk, headers={
                            "Content-Type": "video/mp4",
                            "Content-Range": f"bytes {offset}-{end}/{size}",
                        })
                        if result.status_code == 308:
                            received = result.headers.get("range", "")
                            if not received.startswith("bytes=0-"):
                                raise DriveArchiveError("Google Drive did not confirm upload progress.")
                            next_offset = int(received.split("-")[-1]) + 1
                            if next_offset <= offset or next_offset > size:
                                raise DriveArchiveError("Google Drive upload did not advance.")
                            offset = next_offset
                        else:
                            result.raise_for_status()
                            file_id = result.json()["id"]
                            offset = size
            verification = http.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                headers=headers, params={"fields": "size,md5Checksum", "supportsAllDrives": "true"})
            verification.raise_for_status()
            verified = verification.json()
            if (verified.get("md5Checksum") != checksum
                    or int(verified.get("size", -1)) != video.stat().st_size):
                raise DriveArchiveError("Google Drive returned a different file checksum.")
            receipts[key] = {"id": file_id, "folder_id": folder_id}
            temp = receipts_path.with_suffix(".tmp")
            temp.write_text(json.dumps(receipts))
            os.replace(temp, receipts_path)
