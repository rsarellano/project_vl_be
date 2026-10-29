"""Lemon Squeezy checkout (test mode) and subscription webhooks."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection.database import get_db
from app.controllers.answer_router import get_user_from_request
from app.models.subscription_models.Subscription import Subscription
from app.models.user_models.User import User
from app.services.billing.lemonsqueezy import (
    create_checkout,
    missing_settings,
    test_mode,
    verify_webhook,
)

billing_router = APIRouter(prefix="/billing", tags=["billing"])

_ACTIVE = {"active", "on_trial", "paused"}
_ENDED = {"cancelled", "expired", "unpaid"}


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@billing_router.get("/status")
async def billing_status() -> dict:
    """Whether checkout can be opened. Does not reveal secrets."""
    return {
        "provider": "lemonsqueezy",
        "configured": not missing_settings(),
        "missing": missing_settings(),
        "test_mode": test_mode(),
    }


@billing_router.post("/checkout")
async def start_checkout(
    request: Request,
    user: User = Depends(get_user_from_request),
) -> dict:
    """Create a Lemon Squeezy checkout for the signed-in user."""
    origin = request.headers.get("origin") or "http://localhost:3000"
    redirect_url = f"{origin.rstrip('/')}/upgrade?checkout=done"
    try:
        url = await asyncio.to_thread(
            create_checkout,
            user_id=str(user.id),
            email=user.email,
            redirect_url=redirect_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"url": url, "test_mode": test_mode()}


@billing_router.post("/webhook")
async def lemon_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Apply subscription changes Lemon Squeezy sends after a test payment."""
    raw = await request.body()
    try:
        event = verify_webhook(raw, request.headers.get("x-signature"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Webhook body was not JSON.") from exc

    meta = event.get("meta") if isinstance(event.get("meta"), dict) else {}
    event_name = str(meta.get("event_name") or "")
    custom = meta.get("custom_data") if isinstance(meta.get("custom_data"), dict) else {}
    user_id = custom.get("user_id")
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    attributes = data.get("attributes") if isinstance(data.get("attributes"), dict) else {}

    if not user_id:
        return JSONResponse({"ok": True, "ignored": "no user_id"})
    try:
        user_uuid = uuid.UUID(str(user_id))
    except ValueError:
        return JSONResponse({"ok": True, "ignored": "bad user_id"})

    result = await db.execute(select(Subscription).where(Subscription.user_id == user_uuid))
    sub = result.scalars().first()
    if sub is None:
        sub = Subscription(user_id=user_uuid, tier="free")
        db.add(sub)

    status = str(attributes.get("status") or "")
    if event_name in {"subscription_created", "subscription_updated", "subscription_resumed", "subscription_payment_success"}:
        if status in _ACTIVE or not status:
            sub.tier = "pro"
            sub.started_at = datetime.now(timezone.utc)
            sub.expires_at = _parse_time(attributes.get("renews_at"))
    elif event_name in {"subscription_cancelled", "subscription_expired"} or status in _ENDED:
        sub.tier = "free"
        sub.expires_at = _parse_time(attributes.get("ends_at"))

    lemon_id = data.get("id")
    if lemon_id and hasattr(sub, "lemon_subscription_id"):
        sub.lemon_subscription_id = str(lemon_id)

    await db.commit()
    return JSONResponse({"ok": True, "event": event_name})
