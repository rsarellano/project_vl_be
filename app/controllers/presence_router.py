"""Presence heartbeat — any authenticated user can ping their current path."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection.database import get_db
from app.services.user_services import get_current_user
from app.services.presence_services import heartbeat_presence

presence_router = APIRouter(prefix="/presence", tags=["presence"])


class PresenceHeartbeatBody(BaseModel):
    path: str = Field(default="/", max_length=500)


@presence_router.post("/heartbeat")
async def presence_heartbeat(
    body: PresenceHeartbeatBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user(request, db)
    return await heartbeat_presence(
        user_id=str(user["id"]),
        email=str(user["email"]),
        role=str(user.get("role") or "student"),
        path=body.path or "/",
    )
