"""Google sign-in code exchange helpers, and private SaaSShorts actors.

The Google callback used to put the 30-day session JWT in the redirect's URL
hash. It now hands a single-use code bound to a challenge the dashboard made
in the same tab; the database round trip is exercised against production
after deploy, the rules a request can trip over are pinned here.

Generated actor images used to land in the shared, publicly listed gallery
with the product they were holding in the caption. They now go to a private
prefix per user and come back as presigned URLs.
"""
import base64
import hashlib
import io
import secrets
from datetime import datetime, timezone

import pytest


class TestLoginCodeHelpers:
    @pytest.fixture(autouse=True)
    def _auth(self):
        pytest.importorskip("jwt")
        from cloud import auth
        self.auth = auth

    def test_challenge_is_base64url_sha256_of_the_verifier(self):
        verifier = secrets.token_urlsafe(32)
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        assert self.auth.challenge_for(verifier) == expected
        assert self.auth.valid_challenge(expected)

    def test_challenge_shape_is_checked(self):
        for bad in (None, "", "short", "x" * 44, "a" * 42 + "=", "a" * 42 + "/"):
            assert not self.auth.valid_challenge(bad), bad

    def test_exchange_rejects_malformed_input_before_the_database(self):
        from fastapi import HTTPException
        import asyncio
        for code, verifier in (("", "v" * 43), ("c" * 201, "v" * 43), ("abc", "short")):
            with pytest.raises(HTTPException) as exc:
                asyncio.run(self.auth.exchange_login_code(
                    self.auth.LoginExchangeRequest(code=code, verifier=verifier)))
            assert exc.value.status_code == 400


class TestLoginCodeTable:
    def test_is_erased_with_the_account(self):
        from cloud import account
        from cloud.models import LoginCode
        assert LoginCode in account.USER_OWNED_TABLES


class _FakeS3:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})
        self.presigned = []

    def upload_file(self, path, bucket, key, ExtraArgs=None):
        self.objects[key] = open(path, "rb").read()

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.objects[Key] = Body

    def generate_presigned_url(self, op, Params, ExpiresIn):
        self.presigned.append(Params["Key"])
        return f"https://signed.example/{Params['Key']}?X-Amz-Expires={ExpiresIn}"

    def get_paginator(self, name):
        fake = self

        class _P:
            def paginate(self, Bucket, Prefix):
                when = datetime(2026, 10, 1, tzinfo=timezone.utc)
                yield {"Contents": [{"Key": k, "LastModified": when}
                                    for k in sorted(fake.objects) if k.startswith(Prefix)]}
        return _P()

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key])}


class TestActorStorage:
    @pytest.fixture()
    def s3(self, monkeypatch):
        s3_uploader = pytest.importorskip("s3_uploader")
        fake = _FakeS3({
            "avatars/actor_1_ab12cd34.png": b"png",
            "avatars/actor_1_ab12cd34.json":
                b'{"description": "young woman smiling (holding Acme invoicing app)"}',
        })
        monkeypatch.setattr(s3_uploader, "get_s3_client", lambda: fake)
        monkeypatch.setenv("AWS_S3_PUBLIC_BUCKET", "bucket")
        return s3_uploader, fake

    def test_owned_actor_goes_private_and_comes_back_presigned(self, s3, tmp_path):
        mod, fake = s3
        img = tmp_path / "actor_1.png"
        img.write_bytes(b"x" * 2000)
        url = mod.upload_actor_to_s3(str(img), description="man (holding Acme)", owner_tag="tag123")
        keys = [k for k in fake.objects if k.startswith(mod.PRIVATE_ACTOR_PREFIX)]
        assert {k.rsplit(".", 1)[1] for k in keys} == {"png", "json"}
        assert all(k.startswith(f"{mod.PRIVATE_ACTOR_PREFIX}tag123/") for k in keys)
        assert url.startswith("https://signed.example/private/actors/tag123/")
        assert not any(k.startswith("avatars/actor_1_") and k.endswith(".png") and k != "avatars/actor_1_ab12cd34.png"
                       for k in fake.objects)

    def test_self_host_actor_still_goes_to_the_shared_gallery(self, s3, tmp_path):
        mod, fake = s3
        img = tmp_path / "actor_2.png"
        img.write_bytes(b"x" * 2000)
        url = mod.upload_actor_to_s3(str(img), description="d")
        assert "/avatars/actor_2_" in url

    def test_gallery_strips_the_product_from_shared_captions(self, s3):
        mod, _ = s3
        images = mod.list_actor_gallery()
        assert [i["description"] for i in images] == ["young woman smiling"]

    def test_gallery_shows_the_callers_own_actors_first_and_only_theirs(self, s3, tmp_path):
        mod, fake = s3
        img = tmp_path / "actor_3.png"
        img.write_bytes(b"x" * 2000)
        mod.upload_actor_to_s3(str(img), description="mine (holding Acme)", owner_tag="me")
        mod.upload_actor_to_s3(str(img), description="theirs (holding Other)", owner_tag="them")
        anon = mod.list_actor_gallery()
        assert all("private/" not in i["url"] for i in anon)
        mine = mod.list_actor_gallery("me")
        assert mine[0]["mine"] and mine[0]["description"] == "mine (holding Acme)"
        assert mine[0]["url"].startswith("https://signed.example/private/actors/me/")
        assert not any("/them/" in i["url"] for i in mine)
