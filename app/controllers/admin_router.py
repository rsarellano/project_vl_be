"""Super Admin Access API — gated by users.sa_access."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection.database import get_db
from app.models.user_models.User import User
from app.services.admin_services import get_analytics_snapshot, require_sa_access
from app.services.admin_chart_service import (
    build_chart_from_prompt,
    build_chart_from_spec,
)
from app.services.presence_services import list_presence

admin_router = APIRouter(prefix="/admin", tags=["admin"])

ChartTypeOpt = Literal["bar", "line", "pie", "area"]
MetricOpt = Literal[
    "time_by_subject",
    "time_by_area",
    "time_by_user",
    "users_by_role",
    "users_by_tier",
    "online_by_area",
    "platform_totals",
    "users_over_min_seconds",
]


class ChartPromptBody(BaseModel):
    prompt: str = Field(min_length=3, max_length=500)
    chart_type: Optional[ChartTypeOpt] = None


class ChartBuildBody(BaseModel):
    metric: MetricOpt
    chart_type: ChartTypeOpt = "bar"
    days: int = Field(default=7, ge=1, le=90)
    min_seconds: Optional[int] = Field(default=None, ge=1)
    title: Optional[str] = Field(default=None, max_length=200)


@admin_router.get("/analytics")
async def analytics(
    _: User = Depends(require_sa_access),
    db: AsyncSession = Depends(get_db),
):
    return await get_analytics_snapshot(db)


@admin_router.get("/presence")
async def presence(_: User = Depends(require_sa_access)):
    return await list_presence()


@admin_router.post("/chart")
async def chart_from_prompt(
    body: ChartPromptBody,
    _: User = Depends(require_sa_access),
    db: AsyncSession = Depends(get_db),
):
    prompt = (body.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    result = await build_chart_from_prompt(
        prompt, db, chart_type=body.chart_type
    )
    return result.model_dump()


@admin_router.post("/chart/build")
async def chart_from_spec(
    body: ChartBuildBody,
    _: User = Depends(require_sa_access),
    db: AsyncSession = Depends(get_db),
):
    result = await build_chart_from_spec(
        db,
        metric=body.metric,
        chart_type=body.chart_type,
        days=body.days,
        min_seconds=body.min_seconds,
        title=body.title,
    )
    return result.model_dump()
