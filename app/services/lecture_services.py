"""Lecture persistence + AI generate-and-save + publish."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.lecture_models.Lecture import Lecture
from app.models.user_models.User import User
from app.schemas.lecture_schemas import (
    LectureCreate,
    LectureResponse,
    LectureSummary,
    LectureUpdate,
)
from app.services.ai_services.classroom_assistant_service import generate_lecture_from_prompt
from app.services.lecture_scene import materialize_slides
from app.services.lecture_subjects import normalize_subject


def _slides_as_dicts(slides: list[Any], *, with_scenes: bool = True) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, slide in enumerate(slides, start=1):
        if hasattr(slide, "model_dump"):
            data = slide.model_dump()
        elif isinstance(slide, dict):
            data = dict(slide)
        else:
            continue
        data.setdefault("number", i)
        out.append(data)
    if with_scenes:
        return materialize_slides(out)
    return out


def to_response(lecture: Lecture, *, viewer: User | None = None) -> LectureResponse:
    slides = lecture.slides if isinstance(lecture.slides, list) else []
    is_owner = bool(viewer and lecture.owner_id == viewer.id)
    return LectureResponse(
        id=lecture.id,
        title=lecture.title,
        subject=getattr(lecture, "subject", None) or "general",
        prompt=lecture.prompt if is_owner else None,
        slides=slides,
        is_published=bool(lecture.is_published),
        published_at=lecture.published_at,
        is_owner=is_owner,
        created_at=lecture.created_at,
        updated_at=lecture.updated_at,
    )


def to_summary(lecture: Lecture) -> LectureSummary:
    slides = lecture.slides if isinstance(lecture.slides, list) else []
    return LectureSummary(
        id=lecture.id,
        title=lecture.title,
        subject=getattr(lecture, "subject", None) or "general",
        slide_count=len(slides),
        is_published=bool(lecture.is_published),
        published_at=lecture.published_at,
        created_at=lecture.created_at,
        updated_at=lecture.updated_at,
    )


async def create_lecture(
    body: LectureCreate,
    user: User,
    db: AsyncSession,
) -> Lecture:
    lecture = Lecture(
        owner_id=user.id,
        title=body.title.strip() or "Untitled Lecture",
        subject=normalize_subject(body.subject),
        prompt=body.prompt,
        slides=_slides_as_dicts(body.slides),
        is_published=False,
        published_at=None,
    )
    db.add(lecture)
    await db.commit()
    await db.refresh(lecture)
    return lecture


async def generate_and_save_lecture(
    prompt: str,
    user: User,
    db: AsyncSession,
    *,
    subject: str | None = None,
    topic: str | None = None,
) -> Lecture:
    text = (prompt or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Prompt is required")

    subject_key = normalize_subject(subject)
    draft = await generate_lecture_from_prompt(
        text, subject=subject_key, topic=topic
    )
    title = str(draft.get("title") or "Untitled Lecture").strip() or "Untitled Lecture"
    slides = draft.get("slides") or []
    if not isinstance(slides, list):
        slides = []

    lecture = Lecture(
        owner_id=user.id,
        title=title,
        subject=subject_key,
        prompt=text,
        slides=_slides_as_dicts(slides),
        is_published=False,
        published_at=None,
    )
    db.add(lecture)
    await db.commit()
    await db.refresh(lecture)
    return lecture


async def list_lectures_for_user(user: User, db: AsyncSession) -> list[Lecture]:
    """Owner library: all of their lectures (draft + published)."""
    result = await db.execute(
        select(Lecture)
        .where(Lecture.owner_id == user.id)
        .order_by(Lecture.created_at.desc())
    )
    return list(result.scalars().all())


async def get_lecture_for_user(
    lecture_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> Lecture:
    """Owner-only fetch (edit / delete / publish)."""
    result = await db.execute(
        select(Lecture).where(Lecture.id == lecture_id, Lecture.owner_id == user.id)
    )
    lecture = result.scalars().first()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    return lecture


async def get_lecture_accessible(
    lecture_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> Lecture:
    """
    View access:
    - Owner can always open (draft or published)
    - Others can open only if published
    """
    result = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
    lecture = result.scalars().first()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    is_owner = lecture.owner_id == user.id
    if is_owner or lecture.is_published:
        return lecture

    raise HTTPException(
        status_code=403,
        detail="This lecture is not published yet.",
    )


async def delete_lecture_for_user(
    lecture_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> None:
    lecture = await get_lecture_for_user(lecture_id, user, db)
    await db.delete(lecture)
    await db.commit()


async def update_lecture_for_user(
    lecture_id: uuid.UUID,
    body: LectureUpdate,
    user: User,
    db: AsyncSession,
) -> Lecture:
    lecture = await get_lecture_for_user(lecture_id, user, db)
    if body.title is not None:
        title = body.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        lecture.title = title
    if body.slides is not None:
        lecture.slides = materialize_slides(
            _slides_as_dicts(body.slides, with_scenes=False)
        )
        flag_modified(lecture, "slides")
    if body.subject is not None:
        lecture.subject = normalize_subject(body.subject)
    db.add(lecture)
    await db.commit()
    await db.refresh(lecture)
    return lecture


async def set_lecture_published(
    lecture_id: uuid.UUID,
    user: User,
    db: AsyncSession,
    *,
    published: bool,
) -> Lecture:
    lecture = await get_lecture_for_user(lecture_id, user, db)
    lecture.is_published = published
    lecture.published_at = datetime.now(timezone.utc) if published else None
    db.add(lecture)
    await db.commit()
    await db.refresh(lecture)
    return lecture
