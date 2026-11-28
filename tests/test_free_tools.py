"""Free public tools (free_tools.py): URL parsing, caption track choice,
json3 parsing, the rate limiter and the shape of the generator output.

The network paths (yt-dlp, Gemini) are not exercised here; the prod check
runs them for real. What is pinned down is what decides cost and honesty:
nothing but one video id ever reaches yt-dlp, machine translations are never
served as a transcript, and the limiter refuses before any work is done.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import free_tools as ft


class TestExtractVideoId:
    @pytest.mark.parametrize("url", [
        "https://www.youtube.com/watch?v=arj7oStGLkU",
        "https://youtube.com/watch?v=arj7oStGLkU&t=42s",
        "https://m.youtube.com/watch?v=arj7oStGLkU&list=PL123",
        "youtube.com/watch?v=arj7oStGLkU",
        "https://youtu.be/arj7oStGLkU?si=abc",
        "https://www.youtube.com/shorts/arj7oStGLkU",
        "https://www.youtube.com/live/arj7oStGLkU",
        "https://www.youtube.com/embed/arj7oStGLkU",
        "arj7oStGLkU",
    ])
    def test_single_video_links(self, url):
        assert ft.extract_video_id(url) == "arj7oStGLkU"

    @pytest.mark.parametrize("url", [
        "", "hello", "https://www.youtube.com/playlist?list=PL123",
        "https://www.youtube.com/@ted", "https://www.youtube.com/results?search_query=x",
        "https://evil.example/watch?v=arj7oStGLkU", "https://youtube.com.evil.io/watch?v=arj7oStGLkU",
        "https://www.youtube.com/watch?v=short",
    ])
    def test_everything_else_is_refused(self, url):
        assert ft.extract_video_id(url) is None


def _fmt(name="English"):
    return [{"ext": "json3", "url": "u", "name": name}]


class TestChooseTrack:
    def test_manual_in_spoken_language_wins(self):
        info = {"language": "en", "subtitles": {"es": _fmt("Spanish"), "en": _fmt()},
                "automatic_captions": {"en-orig": _fmt("English (Original)"), "fr": _fmt()}}
        kind, key, langs = ft.choose_track(info)
        assert (kind, key) == ("manual", "en")
        codes = {(l["code"], l["kind"]) for l in langs}
        # auto translations ("fr") are never offered
        assert codes == {("es", "manual"), ("en", "manual"), ("en", "auto")}

    def test_auto_original_when_no_human_track(self):
        info = {"language": "es", "subtitles": {},
                "automatic_captions": {"es-orig": _fmt(), "en": _fmt(), "de": _fmt()}}
        assert ft.choose_track(info)[:2] == ("auto", "es-orig")

    def test_plain_code_auto_track_counts_as_original(self):
        info = {"language": "en", "automatic_captions": {"en": _fmt(), "de": _fmt()}}
        assert ft.choose_track(info)[:2] == ("auto", "en")

    def test_live_chat_is_not_a_caption(self):
        info = {"subtitles": {"live_chat": _fmt()}, "automatic_captions": {}}
        assert ft.choose_track(info)[:2] == (None, None)

    def test_requested_language(self):
        info = {"language": "en", "subtitles": {"es": _fmt(), "en": _fmt()},
                "automatic_captions": {"en-orig": _fmt()}}
        assert ft.choose_track(info, "es")[:2] == ("manual", "es")
        assert ft.choose_track(info, "en-orig")[:2] == ("auto", "en-orig")
        # a translation that is not a real track falls back to the default
        assert ft.choose_track(info, "ja")[:2] == ("manual", "en")


def test_parse_json3_drops_markers_and_clamps_overlaps():
    data = {"events": [
        {"tStartMs": 0, "dDurationMs": 5000},
        {"tStartMs": 100, "dDurationMs": 4000, "segs": [{"utf8": "hello"}, {"utf8": " world"}]},
        {"tStartMs": 2000, "dDurationMs": 10, "aAppend": 1, "segs": [{"utf8": "\n"}]},
        {"tStartMs": 3000, "dDurationMs": 2500, "segs": [{"utf8": "second\nline"}]},
    ]}
    out = ft.parse_json3(data)
    assert out == [
        {"start": 0.1, "dur": 2.9, "text": "hello world"},
        {"start": 3.0, "dur": 2.5, "text": "second line"},
    ]


def test_rate_limiter_per_ip_and_global():
    now = [1000.0]
    lim = ft.RateLimiter({"t": {"per_ip": [(60, 2)], "global_day": 3}}, clock=lambda: now[0])
    assert lim.check("t", "a") is None
    assert lim.check("t", "a") is None
    assert lim.check("t", "a") == "ip"
    assert lim.check("t", "b") is None
    assert lim.check("t", "c") == "global"
    now[0] += 86400
    assert lim.check("t", "c") is None


class TestShapeResult:
    def test_tags_respect_the_500_character_limit(self):
        tags = [f"tag number {i:02d} with padding" for i in range(40)]
        out = ft.shape_result("tags", {"tags": tags + ["#Dup", "dup"]})
        assert out["characters"] <= 500
        assert out["characters"] == len(",".join(out["tags"]))

    def test_tags_are_deduped_and_cleaned(self):
        out = ft.shape_result("tags", {"tags": ["#Procrastination", "procrastination", "tim urban"]})
        assert out["tags"] == ["Procrastination", "tim urban"]

    def test_titles_cut_at_100_and_no_em_dash(self):
        out = ft.shape_result("titles", {"titles": [{"title": "A — B" + "x" * 200, "angle": "how-to"}]})
        t = out["titles"][0]["title"]
        assert len(t) == 100 and "—" not in t

    def test_empty_output_is_an_error(self):
        with pytest.raises(ValueError):
            ft.shape_result("description", {"description": ""})


def test_prompt_carries_the_keyword_and_rules():
    p = ft.build_prompt("titles", "A talk about procrastination", "procrastination", "students")
    assert '"procrastination"' in p and "TARGET AUDIENCE: students" in p
    assert "Do not invent" in p
    p2 = ft.build_prompt("description", "x" * 30)
    assert "write no chapters" in p2


def _client():
    app = FastAPI()
    app.include_router(ft.router)
    return TestClient(app)


def test_transcript_endpoint_rejects_non_video_before_any_work(monkeypatch):
    called = []
    monkeypatch.setattr(ft, "fetch_transcript", lambda *a: called.append(a))
    r = _client().get("/api/tools/youtube-transcript", params={"url": "https://youtube.com/@ted"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "bad_url"
    assert not called


def test_transcript_endpoint_caches_and_maps_errors(monkeypatch):
    ft._TRANSCRIPT_CACHE.clear()
    monkeypatch.setattr(ft, "_limiter", ft.RateLimiter(ft.LIMITS))
    calls = []

    def fake(video_id, lang):
        calls.append(video_id)
        if video_id == "AAAAAAAAAAA":
            raise ft.TranscriptError("no_captions", "none", 404)
        return {"video_id": video_id, "title": "t", "channel": "c", "duration": 10,
                "languages": [], "language": "en", "kind": "manual",
                "segments": [{"start": 0, "dur": 1, "text": "hi"}]}

    monkeypatch.setattr(ft, "fetch_transcript", fake)
    c = _client()
    r1 = c.get("/api/tools/youtube-transcript", params={"url": "https://youtu.be/arj7oStGLkU"})
    r2 = c.get("/api/tools/youtube-transcript", params={"url": "arj7oStGLkU"})
    assert r1.status_code == 200 and r1.json()["cached"] is False
    assert r2.status_code == 200 and r2.json()["cached"] is True
    for _ in range(2):
        r = c.get("/api/tools/youtube-transcript", params={"url": "AAAAAAAAAAA"})
        assert r.status_code == 404 and r.json()["detail"]["code"] == "no_captions"
    assert calls == ["arj7oStGLkU", "AAAAAAAAAAA"]


def test_metadata_endpoint_validates_input(monkeypatch):
    monkeypatch.setattr(ft, "_gemini_key", lambda: "k")
    c = _client()
    assert c.post("/api/tools/youtube-metadata", json={"mode": "x", "topic": "a" * 40}).status_code == 400
    assert c.post("/api/tools/youtube-metadata", json={"mode": "tags", "topic": "short"}).status_code == 400
    monkeypatch.setattr(ft, "_generate", lambda prompt: {"tags": ["a b", "c"]})
    r = c.post("/api/tools/youtube-metadata", json={"mode": "tags", "topic": "A video about sourdough bread at home"})
    assert r.status_code == 200 and r.json()["tags"] == ["a b", "c"]


def test_degraded_response_is_the_route_not_the_video():
    # anonymous answer from a throttled static: title only
    assert ft.is_degraded({"title": "Inside the Mind", "formats": [], "duration": None})
    # a finished 24/7 stream: no formats, but a real player response
    assert not ft.is_degraded({"title": "lofi", "formats": [], "duration": 121601512})
    assert not ft.is_degraded({"formats": [{"id": 1}], "duration": 844})


# --------------------------------------------------------------------------- #
# TikTok transcript
# --------------------------------------------------------------------------- #
class TestExtractTikTokTarget:
    @pytest.mark.parametrize("url", [
        "https://www.tiktok.com/@garyvee/video/7701728720121236749",
        "https://www.tiktok.com/@garyvee/video/7701728720121236749?is_from_webapp=1&sender_device=pc",
        "tiktok.com/@some.user_1/video/7701728720121236749",
        "https://m.tiktok.com/v/7701728720121236749.html",
        "https://www.tiktok.com/embed/v2/7701728720121236749",
        "7701728720121236749",
    ])
    def test_video_links_are_rebuilt_from_the_id(self, url):
        assert ft.extract_tiktok_target(url) == (
            "7701728720121236749", "https://www.tiktok.com/@_/video/7701728720121236749")

    def test_share_links_stay_on_tiktok_hosts(self):
        assert ft.extract_tiktok_target("https://vm.tiktok.com/ZMabc123/") == (
            "vm:ZMabc123", "https://vm.tiktok.com/ZMabc123/")
        assert ft.extract_tiktok_target("vt.tiktok.com/ZSxyz789") == (
            "vt:ZSxyz789", "https://vt.tiktok.com/ZSxyz789/")
        assert ft.extract_tiktok_target("https://www.tiktok.com/t/ZTRC5xgJp/") == (
            "t:ZTRC5xgJp", "https://www.tiktok.com/t/ZTRC5xgJp")

    @pytest.mark.parametrize("url", [
        "", "hello", "https://www.tiktok.com/@garyvee",
        "https://www.tiktok.com/@garyvee/photo/7701728720121236749",
        "https://www.tiktok.com/tag/cooking", "https://www.tiktok.com/music/x-7701728720121236749",
        "https://evil.example/@a/video/7701728720121236749",
        "https://tiktok.com.evil.io/@a/video/7701728720121236749",
        "https://vm.tiktok.com/../../etc", "https://vm.tiktok.com/a/b",
        "https://www.tiktok.com/@a/video/123",
        "https://www.youtube.com/watch?v=arj7oStGLkU",
    ])
    def test_everything_else_is_refused(self, url):
        assert ft.extract_tiktok_target(url) is None


def test_parse_timed_text_vtt_and_srt():
    vtt = ("WEBVTT\n\n\n00:00:00.000 --> 00:00:02.260\nEverybody should <b>go</b>\ncamp\n\n"
           "NOTE a comment\n\n"
           "cue-2\n00:00:02.000 --> 00:00:05.781\nand do a ton\n\n"
           "00:01:05.000 --> 00:01:06.500\n\n")
    assert ft.parse_timed_text(vtt.encode()) == [
        {"start": 0.0, "dur": 2.0, "text": "Everybody should go camp"},
        {"start": 2.0, "dur": 3.781, "text": "and do a ton"},
    ]
    srt = "1\n00:00:01,500 --> 00:00:03,000\nhello\r\n\r\n2\n1:00:00,000 --> 1:00:01,000\nlate"
    assert ft.parse_timed_text(srt) == [
        {"start": 1.5, "dur": 1.5, "text": "hello"},
        {"start": 3600.0, "dur": 1.0, "text": "late"},
    ]


def test_choose_tiktok_track_reads_only_vtt_or_srt():
    info = {"subtitles": {
        "eng-US": [{"ext": "json", "url": "j"}, {"ext": "vtt", "url": "v"}],
        "spa-ES": [{"ext": "srt", "data": "1\n00:00:00,000 --> 00:00:01,000\nhola"}],
        "fra-FR": [{"ext": "json", "url": "j"}],
    }}
    key, fmt, langs = ft.choose_tiktok_track(info)
    assert key == "eng-US" and fmt["url"] == "v"
    assert [l["code"] for l in langs] == ["eng-US", "spa-ES"]
    assert langs[0]["name"] == "English (eng-US)" and langs[0]["kind"] == "tiktok"
    assert ft.choose_tiktok_track(info, "spa-ES")[0] == "spa-ES"
    assert ft.choose_tiktok_track(info, "fra-FR")[0] == "eng-US"
    assert ft.choose_tiktok_track({"subtitles": {}}) == (None, None, [])


def test_tiktok_routes_are_direct_then_statics_never_the_paid_proxy(monkeypatch):
    monkeypatch.setenv("PROXY_URL", "http://paid.invalid:1")
    monkeypatch.delenv("STATIC_PROXY_URLS", raising=False)
    assert ft.tiktok_routes() == [None]
    monkeypatch.setenv("STATIC_PROXY_URLS", "http://s1.invalid:1,http://s2.invalid:1,http://s3.invalid:1")
    routes = ft.tiktok_routes()
    assert routes[0] is None and len(routes) == 3
    assert "http://paid.invalid:1" not in routes
    assert all(r is None or r.startswith("http://s") for r in routes)


class _FakeYDL:
    """Stands in for yt_dlp.YoutubeDL: records the options, answers from a
    script of per-route outcomes."""
    script = []
    seen = []

    def __init__(self, opts):
        self.opts = opts
        _FakeYDL.seen.append(opts)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download):
        assert download is False
        out = _FakeYDL.script.pop(0)
        if isinstance(out, Exception):
            raise out
        return out

    def urlopen(self, url):
        import io
        return io.BytesIO(b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhi there\n")


@pytest.fixture
def fake_ydl(monkeypatch):
    import sys
    import types
    import ssrf_guard
    guarded_calls = []

    class _Guard:
        def __enter__(self):
            guarded_calls.append(True)

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(ssrf_guard, "guarded", lambda: _Guard())
    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=_FakeYDL))
    _FakeYDL.script, _FakeYDL.seen = [], []
    return guarded_calls


_TT_INFO = {"id": "7701728720121236749", "title": "camp", "uploader": "garyvee",
            "channel": "GaryVee", "duration": 43,
            "subtitles": {"eng-US": [{"ext": "vtt", "url": "https://cdn.invalid/c.vtt"}]}}


def test_fetch_tiktok_transcript_options_and_shape(fake_ydl, monkeypatch):
    monkeypatch.setenv("STATIC_PROXY_URLS", "http://s1.invalid:1")
    monkeypatch.setenv("PROXY_URL", "http://paid.invalid:1")
    _FakeYDL.script = [Exception("ERROR: Your IP address is blocked from accessing this post"),
                       dict(_TT_INFO)]
    out = ft.fetch_tiktok_transcript("https://www.tiktok.com/@_/video/7701728720121236749")
    assert out["platform"] == "tiktok" and out["kind"] == "tiktok" and out["language"] == "eng-US"
    assert out["page_url"] == "https://www.tiktok.com/@garyvee/video/7701728720121236749"
    assert out["segments"] == [{"start": 0.0, "dur": 1.0, "text": "hi there"}]
    first, second = _FakeYDL.seen
    assert "proxy" not in first and second["proxy"] == "http://s1.invalid:1"
    for opts in _FakeYDL.seen:
        assert opts["writesubtitles"] and opts["skip_download"] and opts["noplaylist"]
        assert opts["allowed_extractors"] == ["TikTok", "vm.tiktok"]
        assert opts.get("proxy") != "http://paid.invalid:1"
    assert len(fake_ydl) == 2  # every attempt ran inside ssrf_guard.guarded()


def test_fetch_tiktok_transcript_verdicts(fake_ydl, monkeypatch):
    monkeypatch.delenv("STATIC_PROXY_URLS", raising=False)
    _FakeYDL.script = [{**_TT_INFO, "subtitles": {}}]
    with pytest.raises(ft.TranscriptError) as e:
        ft.fetch_tiktok_transcript("https://www.tiktok.com/@_/video/7701728720121236749")
    assert e.value.code == "no_captions"
    _FakeYDL.script = [Exception("ERROR: No suitable extractor found for URL https://www.tiktok.com/?_r=1")]
    with pytest.raises(ft.TranscriptError) as e:
        ft.fetch_tiktok_transcript("https://vm.tiktok.com/ZTR45GpSF/")
    assert e.value.code == "unavailable"
    _FakeYDL.script = [Exception("ERROR: Your IP address is blocked from accessing this post")]
    with pytest.raises(ft.TranscriptError) as e:
        ft.fetch_tiktok_transcript("https://www.tiktok.com/@_/video/7701728720121236749")
    assert e.value.code == "tiktok_blocked" and e.value.status == 503


def test_tiktok_endpoint_rejects_and_caches(monkeypatch):
    ft._TRANSCRIPT_CACHE.clear()
    monkeypatch.setattr(ft, "_limiter", ft.RateLimiter(ft.LIMITS))
    calls = []

    def fake(target_url, lang):
        calls.append(target_url)
        return {"platform": "tiktok", "video_id": "7701728720121236749", "page_url": "p",
                "title": "t", "channel": "c", "duration": 43, "languages": [],
                "language": "eng-US", "kind": "tiktok",
                "segments": [{"start": 0, "dur": 1, "text": "hi"}]}

    monkeypatch.setattr(ft, "fetch_tiktok_transcript", fake)
    c = _client()
    r = c.get("/api/tools/tiktok-transcript", params={"url": "https://www.tiktok.com/@a"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "bad_url"
    assert not calls
    r1 = c.get("/api/tools/tiktok-transcript",
               params={"url": "https://www.tiktok.com/@a/video/7701728720121236749"})
    r2 = c.get("/api/tools/tiktok-transcript", params={"url": "7701728720121236749"})
    assert r1.status_code == 200 and r1.json()["cached"] is False
    assert r2.status_code == 200 and r2.json()["cached"] is True
    assert len(calls) == 1
