"""Super Admin Access — aggregates and auth helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection.database import get_db
from app.models.user_models.User import User
from app.models.classroom_models.Classroom import Classroom
from app.models.classroom_models.ClassroomMembership import ClassroomMembership
from app.models.classroom_models.Assignment import Assignment
from app.models.classroom_models.AssignmentSubmission import AssignmentSubmission
from app.models.ai_models.answer import Answer
from app.models.subscription_models.Subscription import Subscription
from app.services.user_services import get_current_user


async def require_sa_access(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Only users with users.sa_access = TRUE (set manually in DB)."""
    user_dict = await get_current_user(request, db)
    try:
        user_id = uuid.UUID(str(user_dict["id"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid user") from exc
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user or not bool(user.sa_access):
        raise HTTPException(status_code=403, detail="Super Admin Access required")
    return user


async def get_analytics_snapshot(db: AsyncSession) -> dict:
    users_total = (await db.execute(select(sa_func.count()).select_from(User))).scalar() or 0

    role_rows = (
        await db.execute(select(User.role, sa_func.count()).group_by(User.role))
    ).all()
    users_by_role = {str(role or "unknown"): int(count) for role, count in role_rows}

    sa_count = (
        await db.execute(
            select(sa_func.count()).select_from(User).where(User.sa_access.is_(True))
        )
    ).scalar() or 0

    tier_rows = (
        await db.execute(
            select(Subscription.tier, sa_func.count()).group_by(Subscription.tier)
        )
    ).all()
    users_by_tier = {str(tier or "free"): int(count) for tier, count in tier_rows}

    classrooms = (
        await db.execute(select(sa_func.count()).select_from(Classroom))
    ).scalar() or 0
    memberships = (
        await db.execute(select(sa_func.count()).select_from(ClassroomMembership))
    ).scalar() or 0
    assignments = (
        await db.execute(select(sa_func.count()).select_from(Assignment))
    ).scalar() or 0
    submissions = (
        await db.execute(select(sa_func.count()).select_from(AssignmentSubmission))
    ).scalar() or 0
    diagrams = (
        await db.execute(select(sa_func.count()).select_from(Answer))
    ).scalar() or 0

    since = datetime.now(timezone.utc) - timedelta(days=7)
    # Answer.created_at is naive UTC in model; compare loosely
    diagrams_7d = (
        await db.execute(
            select(sa_func.count())
            .select_from(Answer)
            .where(Answer.created_at >= since.replace(tzinfo=None))
        )
    ).scalar() or 0

    try:
        from app.services.usage_time_services import get_usage_time_stats

        usage_time = await get_usage_time_stats(db, days=7)
    except Exception:
        usage_time = {
            "window_days": 7,
            "total_seconds": 0,
            "total_label": "0s",
            "by_subject": [],
            "by_area": [],
            "by_user_subject": [],
        }

    return {
        "users_total": int(users_total),
        "users_by_role": users_by_role,
        "sa_access_count": int(sa_count),
        "users_by_tier": users_by_tier,
        "classrooms": int(classrooms),
        "classroom_memberships": int(memberships),
        "assignments": int(assignments),
        "submissions": int(submissions),
        "diagram_generations": int(diagrams),
        "diagram_generations_7d": int(diagrams_7d),
        "usage_time": usage_time,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
