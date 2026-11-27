"""Discover recent uploads from the private workspace's YouTube channels."""
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx
import yt_dlp

import jobs_db

CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
NS = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


class DiscoveryError(Exception):
    pass



def title_matches_topics(title, topics):
    """Match configured phrases against titles, including GTA 6's common names."""
    normalized = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    for topic in topics.split(","):
        phrase = re.sub(r"[^a-z0-9]+", " ", topic.lower()).strip()
        if not phrase:
            continue
        variants = [phrase]
        if phrase in {"gta 6", "gta vi", "grand theft auto 6", "grand theft auto vi"}:
            variants = ["gta 6", "gta6", "gta vi", "gtavi", "grand theft auto 6", "grand theft auto vi"]
        if any(re.search(r"(?<![a-z0-9])" + re.escape(value) + r"(?![a-z0-9])", normalized)
               for value in variants):
            return True
    return False


def resolve_channel_id(url):
    match = re.fullmatch(r"https://www\.youtube\.com/channel/(UC[A-Za-z0-9_-]{22})", url)
    if match:
        return match.group(1)
    options = {"quiet": True, "no_warnings": True, "extract_flat": True,
               "playlistend": 1, "skip_download": True, "socket_timeout": 15,
               "retries": 0, "extractor_retries": 0}
    with yt_dlp.YoutubeDL(options) as ydl:
        data = ydl.extract_info(url.rstrip("/") + "/videos", download=False)
    candidates = [data.get("channel_id"), data.get("id"), data.get("uploader_id")]
    if data.get("entries"):
        candidates.append(data["entries"][0].get("channel_id"))
    channel_id = next((value for value in candidates if value and CHANNEL_ID.fullmatch(value)), None)
    if not channel_id:
        raise DiscoveryError("Could not identify this channel.")
    return channel_id


def recent_videos(channel_id):
    if not CHANNEL_ID.fullmatch(channel_id):
        raise DiscoveryError("Invalid YouTube channel ID.")
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        with client.stream("GET", "https://www.youtube.com/feeds/videos.xml",
                           params={"channel_id": channel_id}) as response:
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > 1024 * 1024:
                    raise DiscoveryError("The YouTube feed was too large.")
    root = ET.fromstring(content)
    items = []
    for entry in root.findall("atom:entry", NS):
        video_id = entry.findtext("yt:videoId", default="", namespaces=NS)
        if VIDEO_ID.fullmatch(video_id):
            items.append({"id": video_id, "title": entry.findtext("atom:title", default="", namespaces=NS)[:500],
                          "published_at": entry.findtext("atom:published", default="", namespaces=NS)})
    return items


def scan_channel(channel):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with jobs_db._conn() as con:
            state = con.execute("SELECT youtube_id FROM source_channel_state WHERE channel_id=?",
                                (channel["id"],)).fetchone()
        youtube_id = state["youtube_id"] if state and state["youtube_id"] else resolve_channel_id(channel["url"])
        videos = recent_videos(youtube_id)
        with jobs_db._conn() as con:
            # A channel removed during a fetch must not be recreated.
            if not con.execute("SELECT 1 FROM source_channels WHERE id=?", (channel["id"],)).fetchone():
                return
            con.execute("INSERT INTO source_channel_state (channel_id, youtube_id, checked_at, error) "
                        "VALUES (?, ?, ?, NULL) ON CONFLICT(channel_id) DO UPDATE SET "
                        "youtube_id=excluded.youtube_id, checked_at=excluded.checked_at, error=NULL",
                        (channel["id"], youtube_id, now))
            con.executemany(
                "INSERT OR IGNORE INTO source_videos "
                "(video_id, channel_id, title, published_at, discovered_at) VALUES (?, ?, ?, ?, ?)",
                [(v["id"], channel["id"], v["title"], v["published_at"], now) for v in videos])
    except Exception as exc:
        # Do not store raw provider errors which may contain URLs or credentials.
        print(f"Channel discovery failed: {type(exc).__name__}")
        with jobs_db._conn() as con:
            if con.execute("SELECT 1 FROM source_channels WHERE id=?", (channel["id"],)).fetchone():
                con.execute("INSERT INTO source_channel_state (channel_id, checked_at, error) VALUES (?, ?, ?) "
                            "ON CONFLICT(channel_id) DO UPDATE SET checked_at=excluded.checked_at, error=excluded.error",
                            (channel["id"], now, "Could not check this channel. Will retry automatically."))


def refresh_video_stats():
    """Use the optional YouTube Data API to enrich discovery without downloads."""
    key = os.environ.get("YOUTUBE_DATA_API_KEY", "").strip()
    if not key:
        return
    with jobs_db._conn() as con:
        rows = con.execute(
            "SELECT v.video_id FROM source_videos v "
            "LEFT JOIN source_video_stats s ON s.video_id=v.video_id "
            "WHERE s.checked_at IS NULL OR julianday(s.checked_at) < julianday('now', '-6 hours') "
            "ORDER BY v.published_at DESC LIMIT 100"
        ).fetchall()
    ids = [row["video_id"] for row in rows]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for start in range(0, len(ids), 50):
        batch = ids[start:start + 50]
        with httpx.Client(timeout=20) as client:
            response = client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "statistics", "id": ",".join(batch)},
                headers={"X-Goog-Api-Key": key})
            response.raise_for_status()
            items = response.json().get("items", [])
        found = {item["id"]: item.get("statistics", {}) for item in items if item.get("id") in batch}
        with jobs_db._conn() as con:
            for video_id in batch:
                stats = found.get(video_id) or {}
                views = int(stats["viewCount"]) if str(stats.get("viewCount", "")).isdigit() else None
                likes = int(stats["likeCount"]) if str(stats.get("likeCount", "")).isdigit() else None
                con.execute(
                    "INSERT INTO source_video_stats (video_id, views, likes, checked_at) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(video_id) DO UPDATE SET views=excluded.views, likes=excluded.likes, "
                    "checked_at=excluded.checked_at", (video_id, views, likes, now))


def scan_all():
    with jobs_db._conn() as con:
        channels = [dict(row) for row in con.execute("SELECT id, url FROM source_channels").fetchall()]
    for channel in channels:
        scan_channel(channel)
    try:
        refresh_video_stats()
    except Exception as exc:
        print(f"YouTube statistics check failed: {type(exc).__name__}")
