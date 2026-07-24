"""Pydantic schemas for lecture CRUD + AI generate."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LectureSlide(BaseModel):
    number: int = 1
    title: str = ""
    equation: str = ""
    narration: str = ""
    explanation: str = ""
    visual_type: str = "equation"
    slide_role: str = "concept"
    callout: str = ""
    steps: list[str] = Field(default_factory=list)
    scene: Optional[dict[str, Any]] = None


class LectureCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    slides: list[LectureSlide] = Field(default_factory=list)
    prompt: Optional[str] = None
    subject: str = "general"


class LectureGenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    subject: str = Field(default="math", description="math | science | coding | general")
    topic: str | None = Field(
        default=None,
        description="Optional math topic pack: algebra | trigonometry | geometry | functions",
    )


class LectureUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    slides: Optional[list[LectureSlide]] = None
    subject: Optional[str] = None


class LectureResponse(BaseModel):
    id: UUID
    title: str
    subject: str = "general"
    prompt: Optional[str] = None
    slides: list[dict[str, Any]] = Field(default_factory=list)
    is_published: bool = False
    published_at: Optional[datetime] = None
    is_owner: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LectureSummary(BaseModel):
    id: UUID
    title: str
    subject: str = "general"
    slide_count: int
    is_published: bool = False
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LectureEditRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    # Optional unsaved editor draft — AI uses this as the working lecture instead of DB-only.
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    slides: Optional[list[LectureSlide]] = None
    current_slide: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-based slide the educator is currently viewing (for 'this slide')",
    )


class LectureEditResponse(BaseModel):
    message: str
    lecture: Optional[LectureResponse] = None
