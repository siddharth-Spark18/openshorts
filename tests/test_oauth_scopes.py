"""OAuth-issued keys reach what their scope covers, not the whole API.

Every MCP client asks for the default ``openshorts`` scope; the key it gets
must keep driving every MCP tool (they call this API in-process with the same
header) and downloading the results, and nothing else. Hand-made keys keep
the whole API.
"""
import asyncio
import re
from pathlib import Path

import pytest

from cloud import scopes

ROOT = Path(__file__).resolve().parent.parent


class TestNormalise:
    def test_default_when_nothing_or_unknown_is_asked(self):
        assert scopes.normalise(None) == "openshorts"
        assert scopes.normalise("") == "openshorts"
        assert scopes.normalise("admin offline_access") == "openshorts"

    def test_keeps_the_supported_scope_once(self):
        assert scopes.normalise("openshorts openshorts profile") == "openshorts"


class TestEffective:
    def test_hand_made_key_has_no_scope(self):
        assert scopes.effective(None, "my laptop") is None

    def test_oauth_key_from_before_the_column(self):
        assert scopes.effective(None, f"Claude {scopes.OAUTH_KEY_NAME_SUFFIX}") == "openshorts"

    def test_stored_scope_wins(self):
        assert scopes.effective("openshorts", "anything") == "openshorts"


class TestAllows:
    def test_every_path_the_mcp_tools_call_is_allowed(self):
        # Read the tool implementations rather than a hand-kept list, so a new
        # tool calling a new endpoint fails here instead of in production.
        src = (ROOT / "mcp_server.py").read_text()
        calls = re.findall(r'client\.(get|post|put|delete)\(f?"([^"]+)"', src)
        calls += [(m.lower(), p) for m, p in
                  re.findall(r'_job_call\(client, "(GET|POST|PUT|DELETE)", f?"([^"]+)"', src)]
        assert len(calls) >= 8
        for method, path in calls:
            concrete = re.sub(r"\{[^}]+\}", "3f0c2b1e-0000-4000-8000-000000000000", path)
            assert scopes.allows("openshorts", method.upper(), concrete), (method, path)

    def test_mcp_endpoint_and_downloads(self):
        for method, path in [("POST", "/mcp"), ("GET", "/videos/j/clip.mp4"),
                             ("HEAD", "/videos/j/clip.mp4"), ("GET", "/thumbnails/s/t.png"),
                             ("PUT", "/api/uploads/abc-123"), ("GET", "/api/jobs/abc/download-all")]:
            assert scopes.allows("openshorts", method, path), (method, path)

    def test_the_rest_of_the_api_is_out_of_scope(self):
        for method, path in [("DELETE", "/api/projects/abc"), ("PUT", "/api/autopilot"),
                             ("POST", "/api/social/connect"), ("GET", "/api/history"),
                             ("POST", "/api/keys"), ("GET", "/api/status/../keys"),
                             ("POST", "/api/edit"), ("GET", "/api/process")]:
            assert not scopes.allows("openshorts", method, path), (method, path)

    def test_unscoped_key_reaches_everything(self):
        assert scopes.allows(None, "DELETE", "/api/projects/abc")

    def test_unknown_scope_reaches_nothing(self):
        assert not scopes.allows("something-else", "GET", "/api/status/abc")


class TestAuthEnforcement:
    """cloud/auth.get_current_user_optional refuses a scoped key off-scope
    with a clear 403 instead of silently treating it as anonymous."""

    @pytest.fixture()
    def auth(self, monkeypatch):
        pytest.importorskip("jwt")
        from cloud import auth as cloud_auth, api_keys

        async def principal(raw):
            return ("44444444-4444-4444-8444-444444444444", "openshorts")
        monkeypatch.setattr(api_keys, "key_principal", principal)

        class _Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False
        monkeypatch.setattr(cloud_auth.database, "session", lambda: _Session())

        async def load(session, user_id):
            return cloud_auth.CurrentUser(user_id, "a@b.c", entitled=True, plan="pro")
        monkeypatch.setattr(cloud_auth, "_load_current_user", load)
        return cloud_auth

    @staticmethod
    def _request(method, path):
        from starlette.requests import Request
        return Request({"type": "http", "method": method, "path": path, "query_string": b"",
                        "headers": [(b"authorization", b"Bearer osk_test")]})

    def test_in_scope_request_resolves_the_user(self, auth):
        user = asyncio.run(auth.get_current_user_optional(self._request("GET", "/api/status/abc")))
        assert user is not None and user.plan == "pro"

    def test_off_scope_request_is_a_403(self, auth):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(auth.get_current_user_optional(self._request("DELETE", "/api/projects/abc")))
        assert exc.value.status_code == 403
        assert "MCP" in exc.value.detail
