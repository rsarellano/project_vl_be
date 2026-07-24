"""Time spent online, sliced by app area / subject label."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.connection.database import Base


class UsageTimeSlice(Base):
    __tablename__ = "usage_time_slices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    # Product area: tutor | classrooms | lectures | ...
    area = Column(String(64), nullable=False, index=True)
    # Human-readable subject/section, e.g. classroom name or "AI Tutor"
    subject = Column(String(200), nullable=False, default="General", index=True)
    path = Column(String(500), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=False)
    duration_seconds = Column(Integer, nullable=False, default=0)
