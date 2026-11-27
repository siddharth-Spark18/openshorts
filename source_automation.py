"""Choose and claim source videos for automatic processing."""
import uuid
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import jobs_db
from source_discovery import title_matches_topics

NAMESPACE = uuid.UUID("897f0efb-ff15-4fa3-b25e-8c34d2bac3a6")


def enabled():
    return jobs_db.get_setting("source_auto_enabled") != "0"


def video_id_from_url(url):
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        if host == "youtu.be":
            return parsed.path.strip("/").split("/")[0]
        if host == "youtube.com" or host.endswith(".youtube.com"):
            parts = parsed.path.strip("/").split("/")
            if parts[0] in ("shorts", "live", "embed") and len(parts) > 1:
                return parts[1]
            return (parse_qs(parsed.query).get("v") or [None])[0]
    except ValueError:
        return None
    return None


def claim_candidate():
    topics = jobs_db.get_setting("source_topics") or ""
    if not topics or not enabled():
        return None
    with jobs_db._conn() as con:
        con.execute("BEGIN IMMEDIATE")
        lease_owner = str(uuid.uuid4())
        now_epoch = time.time()
        pending = con.execute(
            "SELECT a.video_id,a.job_id FROM source_auto_jobs a "
            "JOIN source_videos v ON v.video_id=a.video_id "
            "JOIN source_channels c ON c.id=v.channel_id "
            "WHERE a.state='pending' AND (a.lease_until IS NULL OR a.lease_until < ?) "
            "ORDER BY a.updated_at LIMIT 1", (now_epoch,)
        ).fetchone()
        if pending:
            con.execute("UPDATE source_auto_jobs SET lease_owner=?, lease_until=? WHERE video_id=?",
                        (lease_owner, now_epoch + 1200, pending["video_id"]))
            return {**dict(pending), "lease_owner": lease_owner}
        if con.execute("SELECT 1 FROM source_auto_jobs a JOIN source_videos v ON v.video_id=a.video_id "
                       "JOIN source_channels c ON c.id=v.channel_id WHERE a.state='pending' LIMIT 1").fetchone():
            return None
        recently_submitted = con.execute(
            "SELECT 1 FROM source_auto_jobs WHERE state='submitted' "
            "AND julianday(updated_at) > julianday('now','-1 day') LIMIT 1"
        ).fetchone()
        if recently_submitted:
            return None
        rows = con.execute(
            "SELECT v.video_id,v.title,v.published_at,s.views "
            "FROM source_videos v JOIN source_channels c ON c.id=v.channel_id "
            "LEFT JOIN source_video_stats s ON s.video_id=v.video_id "
            "LEFT JOIN source_auto_jobs a ON a.video_id=v.video_id "
            "WHERE a.video_id IS NULL ORDER BY v.published_at DESC LIMIT 100"
        ).fetchall()
        existing = {video_id_from_url(row["input_source"] or "") for row in
                    con.execute("SELECT input_source FROM jobs").fetchall()}
        candidates = []
        for row in rows:
            if row["video_id"] in existing or not title_matches_topics(row["title"], topics):
                continue
            rate = -1
            if row["views"] is not None and row["published_at"]:
                try:
                    published = datetime.fromisoformat(row["published_at"].replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - published).total_seconds()
                    rate = row["views"] / max(age / 86400, 1)
                except (ValueError, TypeError):
                    pass
            candidates.append((rate, row["published_at"] or "", row["video_id"]))
        if not candidates:
            return None
        video_id = max(candidates)[2]
        job_id = str(uuid.uuid5(NAMESPACE, video_id))
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        con.execute("INSERT INTO source_auto_jobs (video_id,job_id,state,updated_at,lease_owner,lease_until) VALUES (?,?,?,?,?,?)",
                    (video_id, job_id, "pending", now, lease_owner, now_epoch + 1200))
        return {"video_id": video_id, "job_id": job_id, "lease_owner": lease_owner}


def finish_claim(video_id, state, lease_owner, message=None):
    with jobs_db._conn() as con:
        con.execute("UPDATE source_auto_jobs SET state=?, updated_at=?, message=?, lease_owner=NULL, lease_until=NULL "
                    "WHERE video_id=? AND lease_owner=?",
                    (state, datetime.now(timezone.utc).isoformat(timespec="seconds"), message, video_id, lease_owner))
