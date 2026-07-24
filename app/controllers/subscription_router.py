"""Subscription management endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection.database import get_db
from app.models.subscription_models.Subscription import Subscription
from app.models.user_models.User import User
from app.models.classroom_models.Classroom import Classroom
from app.schemas.subscription_schemas import (
    TierDisplayResponse,
    UpgradeRequest,
    SubscriptionResponse,
    UsageResponse,
)
from app.services.subscription_services.tier_limits import (
    TIER_LIMITS,
    get_all_tiers_display,
    get_limits,
    get_remaining,
)
from app.services.user_services import get_current_user

subscription_router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_user_obj(request: Request, db: AsyncSession) -> User:
    user_dict = await get_current_user(request, db)
    result = await db.execute(select(User).where(User.id == user_dict["id"]))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def _ensure_subscription(user: User, db: AsyncSession) -> Subscription:
    """Return the user's subscription, creating a free one if missing."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    sub = result.scalars().first()
    if not sub:
        sub = Subscription(user_id=user.id, tier="free")
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
    return sub


async def _count_classrooms(user_id, db: AsyncSession) -> int:
    result = await db.execute(
        select(sa_func.count()).where(Classroom.educator_id == user_id)
    )
    return result.scalar() or 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@subscription_router.get("/tiers", response_model=List[TierDisplayResponse])
async def list_tiers():
    """Return all available tiers with display info and limits."""
    tiers_display = get_all_tiers_display()
    result = []
    for td in tiers_display:
        result.append(
            TierDisplayResponse(
                **td,
                limits=get_limits(td["slug"]),
            )
        )
    return result


@subscription_router.get("/my-usage", response_model=UsageResponse)
async def my_usage(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's tier, limits, usage counts, and remaining."""
    user = await _get_user_obj(request, db)
    sub = await _ensure_subscription(user, db)
    limits = get_limits(sub.tier)

    classroom_count = await _count_classrooms(user.id, db)

    usage = {
        "max_classrooms": classroom_count,
        "max_students_per_classroom": 0,  # aggregated on demand
        "max_assignments_per_classroom": 0,
        "max_diagrams_per_day": 0,
    }

    remaining = {}
    for key in limits:
        remaining[key] = get_remaining(sub.tier, key, usage.get(key, 0))

    return UsageResponse(
        tier=sub.tier,
        limits=limits,
        usage=usage,
        remaining=remaining,
    )


@subscription_router.post("/upgrade", response_model=SubscriptionResponse)
async def upgrade(
    body: UpgradeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Mock upgrade — sets the user's tier and expiry."""
    target_tier = body.tier
    if target_tier not in TIER_LIMITS:
        raise HTTPException(status_code=400, detail=f"Unknown tier: {target_tier}")
    if target_tier == "free":
        raise HTTPException(status_code=400, detail="Use the downgrade endpoint to revert to free.")

    billing = (body.billing_period or "month").lower()
    if billing not in ("month", "year"):
        raise HTTPException(status_code=400, detail="billing_period must be 'month' or 'year'")

    user = await _get_user_obj(request, db)
    sub = await _ensure_subscription(user, db)
    sub.tier = target_tier
    sub.started_at = datetime.now(timezone.utc)
    days = 365 if billing == "year" else 30
    sub.expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    await db.commit()

    period_label = "yearly" if billing == "year" else "monthly"
    return SubscriptionResponse(
        success=True,
        tier=sub.tier,
        message=f"Upgraded to {target_tier} ({period_label})!",
    )


@subscription_router.post("/downgrade", response_model=SubscriptionResponse)
async def downgrade(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Revert user to the free tier."""
    user = await _get_user_obj(request, db)
    sub = await _ensure_subscription(user, db)
    sub.tier = "free"
    sub.expires_at = None
    await db.commit()

    return SubscriptionResponse(
        success=True,
        tier="free",
        message="Downgraded to free tier.",
    )
