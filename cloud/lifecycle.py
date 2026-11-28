"""Lifecycle emails: the follow-ups a free sign-up gets on the way to a plan.

Measured on the 30 days to 27-sep-2026: 8.5k sign-ups, ~4.3k with clips, ~400
checkouts started, ~90 paid, and until now not one email in between: no
welcome, no nudge for the half that never clipped anything, nothing after an
abandoned Stripe Checkout (1,011 expired sessions since launch). Four emails,
each at most once per account:

* ``welcome``           — minutes after sign-up.
* ``first_clip``        — 24-72 h after sign-up, nothing processed yet.
* ``winback``           — 2-7 days after the first processed video, no plan.
                          Carries ``WINBACK_PROMO_CODE`` when it is set (a
                          Stripe promotion code; lives in the env, not here,
                          because this repository is public).
* ``checkout_recovery`` — on ``checkout.session.expired`` (billing webhook),
                          with Stripe's recovery URL for the same cart.
* ``paid_idle``         — a paying plan 3+ days into its period with nothing
                          processed in it (and 5+ days left): the minutes and
                          Autopilot, while there is still time to use them.
                          Also goes to plans already set to cancel.
* ``comeback``          — 3+ days after a subscription ended: the free monthly
                          minutes are still theirs. No discount, on purpose.

The two paid ones exist because most first-month cancels come from plans
that never processed a minute after paying.

The first three come from a loop (``TICK_SECONDS``) that sends at most
``BATCH`` per tick, so the backlog on the first deploy drains slowly instead
of hammering the SMTP relay. A ``LifecycleEmail`` row is inserted before each
send; its (user_id, kind) unique constraint is what stops a second container
(during a rolling deploy) or a second tick from sending the same email.

All four are commercial communications: they go through
``emails.send_commercial_email`` (skips unsubscribed accounts, adds the
unsubscribe footer and header). ``LIFECYCLE_EMAILS_DISABLED=1`` turns the loop
and the recovery email off.
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, exists, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from . import config, database, emails, metering
from .models import LifecycleEmail, Subscription, UsageLedger, User

TICK_SECONDS = 10 * 60
BATCH = 30  # emails per tick, all kinds together (~180/h at most)

WELCOME_AFTER = timedelta(minutes=5)
WELCOME_UNTIL = timedelta(hours=24)
FIRST_CLIP_AFTER = timedelta(hours=24)
FIRST_CLIP_UNTIL = timedelta(hours=72)
WINBACK_AFTER = timedelta(hours=48)
WINBACK_UNTIL = timedelta(days=7)
PAID_IDLE_AFTER = timedelta(days=3)   # into the paid period
PAID_IDLE_LEFT = timedelta(days=5)    # still left in it
COMEBACK_AFTER = timedelta(days=3)    # after the subscription ended

# Subscription states that mean "already a customer": no upsell, no nudges.
# ``incomplete`` is left out on purpose: that is a Checkout whose first
# payment failed, exactly who the recovery email is for.
_CUSTOMER_STATES = ("active", "trialing", "past_due", "unpaid")

_is_active = None
_task = None


def disabled() -> bool:
    return os.environ.get("LIFECYCLE_EMAILS_DISABLED", "").lower() in ("1", "true", "yes")


def _now():
    return datetime.now(timezone.utc)


def promo() -> tuple[str, str]:
    """(code, label) of the win-back discount, or ("", "") when unset."""
    code = os.environ.get("WINBACK_PROMO_CODE", "").strip()
    label = os.environ.get("WINBACK_PROMO_LABEL", "").strip()
    return code, (label if code else "")


def amount_label(session_obj: dict) -> str:
    """"$12.00" style label for a Checkout Session, or ""."""
    amount = session_obj.get("amount_total")
    currency = (session_obj.get("currency") or "").upper()
    if not amount or not currency:
        return ""
    value = f"{amount / 100:.2f}"
    return f"${value}" if currency == "USD" else f"{value} {currency}"


def cart_label(session_obj: dict) -> str:
    """What was left in the cart, from the session's metadata: "the Starter
    plan ($12.00)", "60 extra minutes ($9.00)", or "" when it cannot tell."""
    md = session_obj.get("metadata") or {}
    price = amount_label(session_obj)
    suffix = f" ({price})" if price else ""
    if md.get("kind") == "topup" and str(md.get("minutes") or "").isdigit():
        return f"{md['minutes']} extra minutes{suffix}"
    if md.get("plan"):
        return f"the {md['plan'].capitalize()} plan{suffix}"
    return f"your OpenShorts plan{suffix}" if price else ""


async def claim(user_id, kind: str) -> bool:
    """Reserve the right to send ``kind`` to this account. True exactly once."""
    async with database.session() as s:
        async with s.begin():
            row = (await s.execute(
                pg_insert(LifecycleEmail).values(user_id=user_id, kind=kind)
                .on_conflict_do_nothing(constraint="uq_lifecycle_user_kind")
                .returning(LifecycleEmail.id)
            )).first()
    return row is not None


def _not_sent(kind):
    return ~exists().where(and_(LifecycleEmail.user_id == User.id,
                                LifecycleEmail.kind == kind))


def _not_customer():
    return ~exists().where(and_(Subscription.user_id == User.id,
                                Subscription.status.in_(_CUSTOMER_STATES)))


def _processed():
    return exists().where(and_(UsageLedger.user_id == User.id,
                               UsageLedger.job_type == "process",
                               UsageLedger.status.in_(("reserved", "committed"))))


async def _candidates(kind: str, limit: int, now=None):
    """User rows due for ``kind`` right now (oldest first)."""
    now = now or _now()
    q = select(User).where(_not_sent(kind), User.marketing_opt_out.is_(False))
    if kind in ("paid_idle", "comeback"):
        # These two join the (one per user) subscription row and filter on its
        # status directly; _not_customer() would correlate against that join.
        # Comp plans (no Stripe subscription behind them) are not customers.
        q = q.join(Subscription, Subscription.user_id == User.id).where(
            ~Subscription.stripe_subscription_id.like("sub_comp%"))
    else:
        q = q.where(_not_customer())
    if kind == "welcome":
        q = q.where(User.created_at <= now - WELCOME_AFTER,
                    User.created_at >= now - WELCOME_UNTIL)
    elif kind == "first_clip":
        q = q.where(User.created_at <= now - FIRST_CLIP_AFTER,
                    User.created_at >= now - FIRST_CLIP_UNTIL,
                    ~_processed())
    elif kind == "winback":
        first_job = (select(func.min(UsageLedger.created_at))
                     .where(and_(UsageLedger.user_id == User.id,
                                 UsageLedger.job_type == "process",
                                 UsageLedger.status == "committed"))
                     .scalar_subquery())
        q = q.where(first_job <= now - WINBACK_AFTER, first_job >= now - WINBACK_UNTIL)
    elif kind == "paid_idle":
        used = exists().where(and_(UsageLedger.user_id == User.id,
                                   UsageLedger.job_type == "process",
                                   UsageLedger.status.in_(("reserved", "committed")),
                                   UsageLedger.created_at >= Subscription.current_period_start))
        q = q.where(Subscription.status == "active",
                    Subscription.current_period_start <= now - PAID_IDLE_AFTER,
                    Subscription.current_period_end >= now + PAID_IDLE_LEFT,
                    ~used)
    elif kind == "comeback":
        q = q.where(Subscription.status == "canceled",
                    Subscription.last_event_at <= now - COMEBACK_AFTER)
    else:
        raise ValueError(kind)
    async with database.session() as s:
        return list((await s.execute(q.order_by(User.created_at.asc()).limit(limit))).scalars())


async def _subscription(user_id):
    async with database.session() as s:
        return (await s.execute(select(Subscription).where(
            Subscription.user_id == user_id))).scalar_one_or_none()


async def _send(kind: str, user) -> bool:
    # The welcome and first-clip emails promise free minutes: only to accounts
    # that actually have them (not temp-mail, not re-registered after erasure).
    # Claimed first even when skipped, so an ineligible account is not picked
    # up (and does not eat the batch) again on every tick.
    if not await claim(user.id, kind):
        return False
    first_video = config.FIRST_VIDEO_MAX_MINUTES
    if kind in ("welcome", "first_clip"):
        if not metering.free_plan_eligible(user):
            return False
        # A first video already processed (welcome sent late) has no grant left.
        if await metering.has_processed_before(user.id):
            first_video = 0
    if kind == "paid_idle":
        sub = await _subscription(user.id)
        if sub is None or sub.status != "active":
            return False
        return await emails.send_paid_idle_email(
            user.id, user.email, sub.minutes_per_period, sub.current_period_end,
            bool(sub.cancel_at_period_end))
    if kind == "comeback":
        # The email is about the free minutes: only to accounts that get them.
        if not metering.free_plan_eligible(user):
            return False
        return await emails.send_comeback_email(user.id, user.email, config.FREE_PLAN_MINUTES)
    if kind == "welcome":
        return await emails.send_welcome_email(user.id, user.email, first_video)
    if kind == "first_clip":
        return await emails.send_first_clip_email(user.id, user.email, first_video)
    code, label = promo()
    return await emails.send_winback_email(user.id, user.email, code, label)


async def run_once(now=None) -> int:
    """One tick: send up to ``BATCH`` due emails. Returns how many went out."""
    budget = BATCH
    sent = 0
    for kind in ("welcome", "first_clip", "winback", "paid_idle", "comeback"):
        if budget <= 0:
            break
        for user in await _candidates(kind, budget, now):
            if _is_active is not None and not _is_active():
                return sent  # draining for a deploy: the new instance takes over
            try:
                if await _send(kind, user):
                    sent += 1
            except Exception as e:
                print(f"⚠️  Lifecycle {kind} email failed for {user.id}: {e}")
            budget -= 1
            await asyncio.sleep(1)  # be gentle with the SMTP relay
    if sent:
        print(f"✉️  Lifecycle emails sent this tick: {sent}")
    return sent


async def _recovery_target(user_id):
    """The account behind an expired checkout, unless it is gone or already
    paying (it may have paid in another session meanwhile)."""
    async with database.session() as s:
        user = await s.get(User, user_id)
        if user is None:
            return None
        customer = (await s.execute(select(Subscription.id).where(and_(
            Subscription.user_id == user.id,
            Subscription.status.in_(_CUSTOMER_STATES))))).first()
    return None if customer is not None else user


async def on_checkout_expired(session_obj: dict) -> bool:
    """``checkout.session.expired``: mail the recovery link, once per account."""
    if disabled():
        return False
    recovery = ((session_obj.get("after_expiration") or {}).get("recovery") or {})
    url = recovery.get("url")
    user_id = (session_obj.get("client_reference_id")
               or (session_obj.get("metadata") or {}).get("user_id"))
    if not url or not user_id:
        return False
    user = await _recovery_target(user_id)
    if user is None:
        return False
    if not await claim(user.id, "checkout_recovery"):
        return False
    return await emails.send_checkout_recovery_email(
        user.id, user.email, url, cart_label(session_obj))


async def _loop():
    await asyncio.sleep(90)  # let the instance finish booting and resuming jobs
    while True:
        try:
            if _is_active is None or _is_active():
                await run_once()
        except asyncio.CancelledError:
            return
        except Exception as e:
            print(f"⚠️  Lifecycle loop error: {e}")
        await asyncio.sleep(TICK_SECONDS)


def start(is_active=None):
    """Start the loop. ``is_active`` returns False while the instance drains."""
    global _is_active, _task
    _is_active = is_active
    if disabled():
        print("✉️  Lifecycle emails disabled (LIFECYCLE_EMAILS_DISABLED).")
        return
    _task = asyncio.create_task(_loop())
