import json
from uuid import uuid4

import jobs_db
import source_discovery


def test_discovery_deduplicates_and_keeps_existing_items(tmp_path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_DATA_API_KEY", raising=False)
    monkeypatch.setattr(jobs_db, "_DB_PATH", str(tmp_path / "jobs.db"))
    jobs_db.init_db()
    channel = {"id": str(uuid4()), "url": "https://www.youtube.com/@example"}
    with jobs_db._conn() as con:
        con.execute("INSERT INTO source_channels (id,url,created_at) VALUES (?,?,?)",
                    (channel["id"], channel["url"], "2026-01-01"))
    resolved = []
    monkeypatch.setattr(source_discovery, "resolve_channel_id",
                        lambda url: resolved.append(url) or "UC" + "x" * 22)
    monkeypatch.setattr(source_discovery, "recent_videos",
                        lambda _: [{"id": "abcdefghijk", "title": "A video",
                                    "published_at": "2026-01-01T00:00:00Z"}])
    source_discovery.scan_all()
    source_discovery.scan_all()
    with jobs_db._conn() as con:
        assert con.execute("SELECT COUNT(*) FROM source_videos").fetchone()[0] == 1
        state = con.execute("SELECT * FROM source_channel_state").fetchone()
    assert len(resolved) == 1
    assert state["error"] is None


def test_discovery_failure_is_persisted_and_later_cleared(tmp_path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_DATA_API_KEY", raising=False)
    monkeypatch.setattr(jobs_db, "_DB_PATH", str(tmp_path / "jobs.db"))
    jobs_db.init_db()
    channel = {"id": str(uuid4()), "url": "https://www.youtube.com/@example"}
    with jobs_db._conn() as con:
        con.execute("INSERT INTO source_channels (id,url,created_at) VALUES (?,?,?)",
                    (channel["id"], channel["url"], "2026-01-01"))
    def fail(_):
        raise RuntimeError("private provider detail")
    monkeypatch.setattr(source_discovery, "resolve_channel_id", fail)
    source_discovery.scan_all()
    with jobs_db._conn() as con:
        error = con.execute("SELECT error FROM source_channel_state").fetchone()["error"]
    assert "private provider detail" not in error
    monkeypatch.setattr(source_discovery, "resolve_channel_id", lambda _: "UC" + "x" * 22)
    monkeypatch.setattr(source_discovery, "recent_videos", lambda _: [])
    source_discovery.scan_all()
    with jobs_db._conn() as con:
        assert con.execute("SELECT error FROM source_channel_state").fetchone()["error"] is None


def test_youtube_feed_is_parsed_and_invalid_ids_are_ignored(monkeypatch):
    import httpx

    xml = b"""<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:yt="http://www.youtube.com/xml/schemas/2015">
      <entry><yt:videoId>abcdefghijk</yt:videoId><title>First</title>
        <published>2026-11-27T00:00:00Z</published></entry>
      <entry><yt:videoId>invalid</yt:videoId><title>Bad</title></entry>
    </feed>"""
    original = httpx.Client
    def client_factory(**kwargs):
        return original(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=xml)), **kwargs)
    monkeypatch.setattr(source_discovery.httpx, "Client", client_factory)
    assert source_discovery.recent_videos("UC" + "x" * 22) == [
        {"id": "abcdefghijk", "title": "First", "published_at": "2026-11-27T00:00:00Z"}]


def test_gta_topic_matches_common_variants_without_partial_word_matches():
    for title in ["GTA 6 trailer", "GTA6 news", "GTA VI gameplay", "Grand Theft Auto VI news"]:
        assert source_discovery.title_matches_topics(title, "GTA 6")
    assert not source_discovery.title_matches_topics("gta 60 discussion", "GTA 6")
    assert not source_discovery.title_matches_topics("Another gaming video", "GTA 6")


def test_youtube_statistics_are_batched_and_cached(tmp_path, monkeypatch):
    import httpx
    monkeypatch.setattr(jobs_db, "_DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.setenv("YOUTUBE_DATA_API_KEY", "example-key")
    jobs_db.init_db()
    with jobs_db._conn() as con:
        con.execute("INSERT INTO source_videos VALUES (?,?,?,?,?)",
                    ("abcdefghijk", "channel", "Title", "2026-11-27T00:00:00Z", "2026-11-27"))
    calls = []
    original = httpx.Client
    def handler(request):
        calls.append(request)
        assert request.headers["x-goog-api-key"] == "example-key"
        return httpx.Response(200, json={"items": [{"id": "abcdefghijk",
                              "statistics": {"viewCount": "500", "likeCount": "12"}}]})
    monkeypatch.setattr(source_discovery.httpx, "Client",
                        lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    source_discovery.refresh_video_stats()
    source_discovery.refresh_video_stats()
    with jobs_db._conn() as con:
        row = con.execute("SELECT views, likes FROM source_video_stats").fetchone()
    assert (row["views"], row["likes"]) == (500, 12)
    assert len(calls) == 1
