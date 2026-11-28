"""Money moves only with a dashboard session, never with an API key.

An ``osk_`` key (and every OAuth token, which is one) is what agents and
third-party MCP clients hold; the consent screen promises them "no billing".
Cancelling, resuming, ending a trial (charges the card now), the Stripe
portal and the invoices refuse it."""
import asyncio
import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from cloud import auth


def _request(headers):
    return SimpleNamespace(headers=headers)


@pytest.mark.parametrize("headers", [
    {"Authorization": "Bearer osk_" + "a" * 40},
    {"X-API-Key": "osk_" + "a" * 40},
])
def test_api_keys_are_refused(headers):
    with pytest.raises(HTTPException) as e:
        asyncio.run(auth.get_session_user_required(_request(headers)))
    assert e.value.status_code == 403


def test_a_session_passes_through(monkeypatch):
    async def _user(request):
        return "the user"
    monkeypatch.setattr(auth, "get_current_user_required", _user)
    out = asyncio.run(auth.get_session_user_required(_request({"Authorization": "Bearer eyJ.x.y"})))
    assert out == "the user"


def test_billing_endpoints_are_session_only():
    billing = pytest.importorskip("cloud.billing")
    cancellation = pytest.importorskip("cloud.cancellation")
    for fn in (billing.end_trial, billing.create_portal, billing.list_invoices,
               cancellation.retention_offer, cancellation.accept_retention_offer,
               cancellation.resume_subscription, cancellation.cancel_subscription):
        src = inspect.getsource(fn)
        assert "get_session_user_required" in src, fn.__name__
        assert "get_current_user_required" not in src, fn.__name__


def test_top_ups_are_credited_only_once_paid(monkeypatch):
    billing = pytest.importorskip("cloud.billing")
    credited = []

    async def _apply(obj):
        credited.append(obj["id"])
    monkeypatch.setattr(billing, "_apply_topup", _apply)

    def event(etype, sid, status):
        return {"type": etype, "created": 1_700_000_000,
                "data": {"object": {"id": sid, "mode": "payment", "payment_status": status}}}

    asyncio.run(billing.handle_event(event("checkout.session.completed", "cs_card", "paid")))
    asyncio.run(billing.handle_event(event("checkout.session.completed", "cs_debit", "unpaid")))
    asyncio.run(billing.handle_event(event("checkout.session.async_payment_succeeded", "cs_debit", "paid")))
    asyncio.run(billing.handle_event(event("checkout.session.async_payment_failed", "cs_fail", "unpaid")))
    assert credited == ["cs_card", "cs_debit"]


def test_webhook_refuses_to_run_without_a_secret(monkeypatch):
    billing = pytest.importorskip("cloud.billing")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    app = FastAPI()
    app.include_router(billing.router)
    r = TestClient(app).post("/api/stripe/webhook", content=b"{}", headers={"stripe-signature": "x"})
    assert r.status_code == 503
