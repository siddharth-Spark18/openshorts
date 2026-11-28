"""Who may read /videos and /thumbnails in cloud mode.

The job id used to be the only lock on a job's clips and on the untouched
source next to them. Cloud requests now need a path signature, the owner's
media token (query or cookie) or the owner's own credentials; bare links to
jobs older than the signing cutoff keep working through a grace period.
Self-host stays open. app.py freezes BILLING_ENABLED at import, so these tests
flip the module globals the hook reads.
"""
import asyncio
import time

import httpx
import pytest

app_module = pytest.importorskip("app")
import media_auth  # noqa: E402

SECRET = "test-media-secret"
OWNER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
JOB = "33333333-3333-4333-8333-333333333333"
CLIP = f"/videos/{JOB}/clip_1.mp4"


class _User:
    def __init__(self, uid):
        self.id = uid
        self.plan = "pro"


def _get(path, headers=None, cookies=None):
    async def _do():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver",
                                     cookies=cookies or {}) as client:
            return await client.get(path, headers=headers or {})
    return asyncio.run(_do())


@pytest.fixture()
def cloud(tmp_path, monkeypatch):
    out = tmp_path / "output"
    job_dir = out / JOB
    job_dir.mkdir(parents=True)
    (job_dir / "clip_1.mp4").write_bytes(b"clip bytes")
    (job_dir / "source.mp4").write_bytes(b"source bytes")
    (job_dir / ".owner").write_text(OWNER)
    monkeypatch.setattr(app_module, "OUTPUT_DIR", str(out))
    # The mount was built with the import-time directory; point it here too.
    for route in app_module.app.routes:
        if getattr(route, "path", None) == "/videos":
            monkeypatch.setattr(route.app, "directory", str(out))
            monkeypatch.setattr(route.app, "all_directories", [str(out)])
    monkeypatch.setattr(app_module, "BILLING_ENABLED", True)
    monkeypatch.setattr(app_module, "_media_secret", lambda: SECRET)

    async def fake_user(request):
        auth = request.headers.get("authorization", "")
        return _User(auth.split()[-1]) if auth else None
    monkeypatch.setattr(app_module, "_user_from_request", fake_user)

    project = {"row": (None, None)}

    async def fake_project(job_id):
        return project["row"]
    monkeypatch.setattr(app_module, "_media_project", fake_project)
    yield project
    app_module.jobs.pop(JOB, None)


class TestCloudMedia:
    def test_bare_link_to_a_new_job_is_refused(self, cloud):
        resp = _get(CLIP)
        assert resp.status_code == 403
        assert "signature" in resp.json()["detail"]

    def test_the_source_next_to_the_clips_is_refused_too(self, cloud):
        assert _get(f"/videos/{JOB}/source.mp4").status_code == 403

    def test_signed_link_works_without_any_session(self, cloud):
        assert _get(media_auth.sign_media_url(CLIP, SECRET)).status_code == 200

    def test_signature_is_bound_to_one_file(self, cloud):
        signed = media_auth.sign_media_url(CLIP, SECRET)
        other = signed.replace("clip_1.mp4", "source.mp4")
        assert _get(other).status_code == 403

    def test_expired_signature_is_refused(self, cloud):
        exp = int(time.time()) - 5
        sig = media_auth.path_signature(f"videos/{JOB}/clip_1.mp4", exp, SECRET)
        assert _get(f"{CLIP}?exp={exp}&sig={sig}").status_code == 403

    def test_owner_media_token_in_query(self, cloud):
        token = media_auth.mint_user_token(OWNER, SECRET)
        assert _get(f"{CLIP}?mt={token}").status_code == 200

    def test_someone_elses_media_token_is_refused(self, cloud):
        token = media_auth.mint_user_token(OTHER, SECRET)
        assert _get(f"{CLIP}?mt={token}").status_code == 403

    def test_owner_media_cookie(self, cloud):
        token = media_auth.mint_user_token(OWNER, SECRET)
        resp = _get(CLIP, cookies={media_auth.MEDIA_COOKIE_NAME: token})
        assert resp.status_code == 200

    def test_stale_query_token_falls_back_to_the_cookie(self, cloud):
        stale = media_auth.mint_user_token(OWNER, "another-secret")
        fresh = media_auth.mint_user_token(OWNER, SECRET)
        resp = _get(f"{CLIP}?mt={stale}", cookies={media_auth.MEDIA_COOKIE_NAME: fresh})
        assert resp.status_code == 200

    def test_owner_api_key_header(self, cloud):
        assert _get(CLIP, headers={"Authorization": f"Bearer {OWNER}"}).status_code == 200

    def test_other_users_header_is_refused(self, cloud):
        assert _get(CLIP, headers={"Authorization": f"Bearer {OTHER}"}).status_code == 403

    def test_owner_from_the_live_job_record(self, cloud, tmp_path):
        (tmp_path / "output" / JOB / ".owner").unlink()
        app_module.jobs[JOB] = {"user_id": OWNER, "status": "completed", "logs": []}
        token = media_auth.mint_user_token(OWNER, SECRET)
        assert _get(f"{CLIP}?mt={token}").status_code == 200

    def test_hidden_files_stay_hidden_even_signed(self, cloud):
        assert _get(media_auth.sign_media_url(f"/videos/{JOB}/.owner", SECRET)).status_code == 404

    def test_legacy_link_to_an_old_job_inside_the_grace(self, cloud, monkeypatch):
        cutoff = time.time() + 3600
        monkeypatch.setattr(app_module, "_MEDIA_LEGACY_CUTOFF", cutoff)
        monkeypatch.setattr(app_module, "_MEDIA_LEGACY_UNTIL", time.time() + 7200)
        cloud["row"] = (OWNER, cutoff - 86400)
        assert _get(CLIP).status_code == 200

    def test_legacy_grace_ends(self, cloud, monkeypatch):
        monkeypatch.setattr(app_module, "_MEDIA_LEGACY_CUTOFF", time.time() + 3600)
        monkeypatch.setattr(app_module, "_MEDIA_LEGACY_UNTIL", time.time() - 1)
        cloud["row"] = (OWNER, time.time() - 86400)
        assert _get(CLIP).status_code == 403

    def test_job_made_after_the_cutoff_gets_no_grace(self, cloud, monkeypatch):
        monkeypatch.setattr(app_module, "_MEDIA_LEGACY_CUTOFF", time.time() - 3600)
        monkeypatch.setattr(app_module, "_MEDIA_LEGACY_UNTIL", time.time() + 7200)
        cloud["row"] = (OWNER, time.time())
        assert _get(CLIP).status_code == 403


class TestSelfHost:
    def test_open_without_billing(self, tmp_path, monkeypatch):
        out = tmp_path / "output"
        (out / JOB).mkdir(parents=True)
        (out / JOB / "clip_1.mp4").write_bytes(b"clip bytes")
        for route in app_module.app.routes:
            if getattr(route, "path", None) == "/videos":
                monkeypatch.setattr(route.app, "directory", str(out))
                monkeypatch.setattr(route.app, "all_directories", [str(out)])
        assert app_module._media_secret() == ""
        assert _get(CLIP).status_code == 200


class TestHandedOutLinks:
    def test_status_result_gets_signed_download_urls_without_touching_the_job(self, monkeypatch):
        monkeypatch.setattr(app_module, "_media_secret", lambda: SECRET)
        monkeypatch.setenv("PUBLIC_API_URL", "https://api.example.test")
        result = {"clips": [{"video_url": CLIP, "title": "a"}]}
        out = app_module._with_download_urls(result)
        url = out["clips"][0]["download_url"]
        assert url.startswith(f"https://api.example.test{CLIP}?exp=")
        assert "download_url" not in result["clips"][0]
        rel = url[len("https://api.example.test"):]
        q = dict(p.split("=") for p in rel.split("?", 1)[1].split("&"))
        assert media_auth.verify_path_signature(f"videos/{JOB}/clip_1.mp4", q["exp"], q["sig"], SECRET)

    def test_status_result_unchanged_in_self_host(self):
        result = {"clips": [{"video_url": CLIP}]}
        assert app_module._with_download_urls(result) is result

    def test_mcp_clip_urls_are_signed_and_absolute(self, monkeypatch):
        import mcp_server
        monkeypatch.setattr(mcp_server, "_media_secret", lambda: SECRET)
        monkeypatch.setenv("PUBLIC_API_URL", "https://api.example.test")
        clips = mcp_server._clip_summaries(JOB, {"clips": [{"video_url": CLIP, "start": 0, "end": 10}]})
        assert clips[0]["video_url"].startswith(f"https://api.example.test{CLIP}?exp=")
        edited = mcp_server._with_download_url({"new_video_url": CLIP})
        assert edited["download_url"].startswith(f"https://api.example.test{CLIP}?exp=")

    def test_mcp_clip_urls_plain_in_self_host(self, monkeypatch):
        import mcp_server
        monkeypatch.setattr(mcp_server, "_media_secret", lambda: "")
        monkeypatch.setenv("PUBLIC_API_URL", "https://api.example.test")
        clips = mcp_server._clip_summaries(JOB, {"clips": [{"video_url": CLIP}]})
        assert clips[0]["video_url"] == f"https://api.example.test{CLIP}"


class TestMediaToken:
    def test_issues_token_and_cookie_for_the_caller(self, monkeypatch):
        monkeypatch.setattr(app_module, "_media_secret", lambda: SECRET)

        async def fake_user(request):
            return _User(OWNER)
        monkeypatch.setattr(app_module, "_user_from_request", fake_user)

        async def _do():
            transport = httpx.ASGITransport(app=app_module.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
                return await c.post("/api/media-token")
        resp = asyncio.run(_do())
        assert resp.status_code == 200
        token = resp.json()["token"]
        assert media_auth.verify_user_token(token, SECRET) == OWNER
        cookie = resp.headers.get("set-cookie", "")
        assert cookie.startswith(f"{media_auth.MEDIA_COOKIE_NAME}=")
        assert "HttpOnly" in cookie and "samesite=lax" in cookie.lower()

    def test_anonymous_caller_gets_401(self, monkeypatch):
        monkeypatch.setattr(app_module, "_media_secret", lambda: SECRET)

        async def no_user(request):
            return None
        monkeypatch.setattr(app_module, "_user_from_request", no_user)

        async def _do():
            transport = httpx.ASGITransport(app=app_module.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
                return await c.post("/api/media-token")
        assert asyncio.run(_do()).status_code == 401


class TestRenderBody:
    def test_media_token_is_dropped_from_the_render_video_url(self, monkeypatch):
        monkeypatch.setattr(app_module, "BILLING_ENABLED", True)
        monkeypatch.setattr(app_module, "_job_record", lambda job_id: {"user_id": None})

        async def no_check(request, record):
            return None
        monkeypatch.setattr(app_module, "_assert_job_owner", no_check)
        body = {"jobId": JOB, "props": {
            "durationInFrames": 30, "fps": 30, "width": 1080, "height": 1920,
            "videoUrl": f"https://api.example.test{CLIP}?mt=abc.123.def"}}
        asyncio.run(app_module._check_render_body(None, body))
        assert body["props"]["videoUrl"] == f"https://api.example.test{CLIP}"
