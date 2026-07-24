"""Prompt → allowlisted chart spec → data for Recharts (SA Access only)."""

from __future__ import annotations

import os
import re
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics_models.UsageTimeSlice import UsageTimeSlice
from app.models.user_models.User import User
from app.services.admin_services import get_analytics_snapshot
from app.services.presence_services import list_presence
from app.services.usage_time_services import get_usage_time_stats

ChartType = Literal["bar", "line", "pie", "area"]
Metric = Literal[
    "time_by_subject",
    "time_by_area",
    "time_by_user",
    "users_by_role",
    "users_by_tier",
    "online_by_area",
    "platform_totals",
    "users_over_min_seconds",
]


class ChartIntent(BaseModel):
    title: str = Field(description="Short chart title")
    chart_type: ChartType = Field(description="Recharts chart type")
    metric: Metric = Field(description="Which allowlisted dataset to load")
    min_seconds: int | None = Field(
        default=None,
        description="For users_over_min_seconds: minimum total seconds (e.g. 60 for 1 minute)",
    )
    days: int = Field(default=7, description="Lookback window in days (1-90)")
    message: str = Field(description="One sentence explaining what the chart shows")


class ChartPromptResult(BaseModel):
    title: str
    chart_type: ChartType
    metric: Metric
    message: str
    data: list[dict[str, Any]]
    days: int = 7
    min_seconds: int | None = None


SYSTEM_PROMPT = """You convert an admin analytics prompt into a chart request for Project VL.

You may ONLY choose from these metrics:
- time_by_subject: time spent grouped by subject/section
- time_by_area: time spent grouped by app area (tutor, classrooms, ...)
- time_by_user: total time spent per user
- users_by_role: count of users by role
- users_by_tier: count of users by subscription tier
- online_by_area: currently online users by area
- platform_totals: high-level platform counts (users, classrooms, assignments, ...)
- users_over_min_seconds: users whose total tracked time is at least min_seconds

Chart types: bar, line, pie, area.
Prefer bar for comparisons, pie for shares, line for ordered series if relevant.
If the user says "more than 1 minute", set metric=users_over_min_seconds and min_seconds=60.
If "more than N minutes", min_seconds = N * 60.
days defaults to 7 unless the user specifies otherwise (clamp 1-90).
"""


def _openai_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY")


def _assistant_model() -> str:
    return os.getenv("OPENAI_ANSWER_MODEL", "gpt-4o-mini")


def _heuristic_intent(prompt: str) -> ChartIntent:
    """Fallback when OpenAI is unavailable."""
    p = prompt.lower()
    days = 7
    m = re.search(r"(\d+)\s*day", p)
    if m:
        days = max(1, min(90, int(m.group(1))))

    min_seconds = None
    mm = re.search(r"(?:more than|over|at least|>=)\s*(\d+)\s*min", p)
    if mm:
        min_seconds = int(mm.group(1)) * 60
    ms = re.search(r"(?:more than|over|at least|>=)\s*(\d+)\s*sec", p)
    if ms:
        min_seconds = int(ms.group(1))
    if "1 minute" in p or "one minute" in p:
        min_seconds = min_seconds or 60

    if min_seconds is not None or ("logged" in p and "min" in p):
        return ChartIntent(
            title=f"Users with ≥{(min_seconds or 60) // 60}m tracked time",
            chart_type="bar",
            metric="users_over_min_seconds",
            min_seconds=min_seconds or 60,
            days=days,
            message="Users whose total tracked time meets the threshold.",
        )
    if "online" in p or "logged in" in p and "now" in p:
        return ChartIntent(
            title="Online users by area",
            chart_type="pie",
            metric="online_by_area",
            days=days,
            message="Currently online users by app area.",
        )
    if "role" in p:
        return ChartIntent(
            title="Users by role",
            chart_type="pie",
            metric="users_by_role",
            days=days,
            message="User counts by role.",
        )
    if "tier" in p or "subscription" in p or "pro" in p:
        return ChartIntent(
            title="Users by subscription tier",
            chart_type="pie",
            metric="users_by_tier",
            days=days,
            message="User counts by subscription tier.",
        )
    if "area" in p:
        return ChartIntent(
            title="Time spent by area",
            chart_type="bar",
            metric="time_by_area",
            days=days,
            message="Tracked time by app area.",
        )
    if "user" in p and "time" in p:
        return ChartIntent(
            title="Time spent by user",
            chart_type="bar",
            metric="time_by_user",
            days=days,
            message="Total tracked time per user.",
        )
    if "total" in p or "platform" in p:
        return ChartIntent(
            title="Platform totals",
            chart_type="bar",
            metric="platform_totals",
            days=days,
            message="High-level platform counts.",
        )
    return ChartIntent(
        title="Time spent by subject",
        chart_type="bar",
        metric="time_by_subject",
        days=days,
        message="Tracked time by subject/section.",
    )


async def _parse_intent(prompt: str) -> ChartIntent:
    api_key = _openai_api_key()
    if not api_key:
        return _heuristic_intent(prompt)

    try:
        llm = ChatOpenAI(temperature=0, model=_assistant_model(), api_key=api_key)
        structured = llm.with_structured_output(ChartIntent, method="function_calling")
        intent: ChartIntent = await structured.ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )
        intent.days = max(1, min(90, int(intent.days or 7)))
        if intent.metric == "users_over_min_seconds" and not intent.min_seconds:
            intent.min_seconds = 60
        return intent
    except Exception:
        return _heuristic_intent(prompt)


async def _users_over_min_seconds(
    db: AsyncSession, *, days: int, min_seconds: int
) -> list[dict[str, Any]]:
    from datetime import datetime, timedelta, timezone

    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        await db.execute(
            select(
                UsageTimeSlice.user_id,
                sa_func.sum(UsageTimeSlice.duration_seconds),
            )
            .where(UsageTimeSlice.ended_at >= since)
            .group_by(UsageTimeSlice.user_id)
            .having(sa_func.sum(UsageTimeSlice.duration_seconds) >= min_seconds)
            .order_by(sa_func.sum(UsageTimeSlice.duration_seconds).desc())
        )
    ).all()

    if not rows:
        return []

    user_ids = [r[0] for r in rows]
    users = (
        await db.execute(select(User).where(User.id.in_(user_ids)))
    ).scalars().all()
    email_map = {u.id: u.email for u in users}

    return [
        {
            "name": email_map.get(uid, str(uid)[:8]),
            "value": int(total or 0),
            "minutes": round(int(total or 0) / 60, 1),
        }
        for uid, total in rows
    ]


METRIC_TITLES: dict[str, str] = {
    "time_by_subject": "Time spent by subject",
    "time_by_area": "Time spent by area",
    "time_by_user": "Time spent by user",
    "users_by_role": "Users by role",
    "users_by_tier": "Users by subscription tier",
    "online_by_area": "Online users by area",
    "platform_totals": "Platform totals",
    "users_over_min_seconds": "Users over time threshold",
}


async def build_chart_from_spec(
    db: AsyncSession,
    *,
    metric: Metric,
    chart_type: ChartType = "bar",
    days: int = 7,
    min_seconds: int | None = None,
    title: str | None = None,
    message: str | None = None,
) -> ChartPromptResult:
    days = max(1, min(90, int(days or 7)))
    if chart_type not in ("bar", "line", "pie", "area"):
        chart_type = "bar"
    data: list[dict[str, Any]] = []

    if metric == "time_by_subject":
        usage = await get_usage_time_stats(db, days=days)
        data = [
            {"name": row["subject"], "value": int(row["seconds"])}
            for row in usage.get("by_subject") or []
        ]
    elif metric == "time_by_area":
        usage = await get_usage_time_stats(db, days=days)
        data = [
            {"name": row["area"], "value": int(row["seconds"])}
            for row in usage.get("by_area") or []
        ]
    elif metric == "time_by_user":
        usage = await get_usage_time_stats(db, days=days)
        totals: dict[str, int] = {}
        labels: dict[str, str] = {}
        for row in usage.get("by_user_subject") or []:
            uid = str(row.get("user_id") or "")
            totals[uid] = totals.get(uid, 0) + int(row.get("seconds") or 0)
            labels[uid] = str(row.get("email") or uid[:8])
        data = [
            {"name": labels[uid], "value": seconds}
            for uid, seconds in sorted(totals.items(), key=lambda x: x[1], reverse=True)
        ]
    elif metric == "users_by_role":
        snap = await get_analytics_snapshot(db)
        data = [
            {"name": role, "value": count}
            for role, count in (snap.get("users_by_role") or {}).items()
        ]
    elif metric == "users_by_tier":
        snap = await get_analytics_snapshot(db)
        data = [
            {"name": tier, "value": count}
            for tier, count in (snap.get("users_by_tier") or {}).items()
        ]
    elif metric == "online_by_area":
        presence = await list_presence()
        data = [
            {"name": area, "value": count}
            for area, count in (presence.get("by_area") or {}).items()
        ]
    elif metric == "platform_totals":
        snap = await get_analytics_snapshot(db)
        data = [
            {"name": "Users", "value": snap.get("users_total", 0)},
            {"name": "Classrooms", "value": snap.get("classrooms", 0)},
            {"name": "Memberships", "value": snap.get("classroom_memberships", 0)},
            {"name": "Assignments", "value": snap.get("assignments", 0)},
            {"name": "Submissions", "value": snap.get("submissions", 0)},
            {"name": "Diagrams", "value": snap.get("diagram_generations", 0)},
        ]
    elif metric == "users_over_min_seconds":
        threshold = int(min_seconds or 60)
        data = await _users_over_min_seconds(db, days=days, min_seconds=threshold)
        if not title:
            title = f"Users with ≥{threshold // 60}m tracked time"

    resolved_title = (title or METRIC_TITLES.get(metric) or metric).strip()
    resolved_message = (
        message
        or f"{resolved_title} · last {days} day{'s' if days != 1 else ''}"
    )

    resolved_min = (
        int(min_seconds or 60) if metric == "users_over_min_seconds" else None
    )

    return ChartPromptResult(
        title=resolved_title,
        chart_type=chart_type,
        metric=metric,
        message=resolved_message,
        data=data,
        days=days,
        min_seconds=resolved_min,
    )


async def build_chart_from_prompt(
    prompt: str,
    db: AsyncSession,
    *,
    chart_type: ChartType | None = None,
) -> ChartPromptResult:
    intent = await _parse_intent(prompt.strip())
    return await build_chart_from_spec(
        db,
        metric=intent.metric,
        chart_type=chart_type if chart_type in ("bar", "line", "pie", "area") else intent.chart_type,
        days=intent.days,
        min_seconds=intent.min_seconds,
        title=intent.title,
        message=intent.message,
    )
