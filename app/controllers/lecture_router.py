"""Lecture library API — persist AI-generated and manual lectures."""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.connection.database import get_db
from app.models.user_models.User import User
from app.schemas.lecture_schemas import (
    LectureClarifyRequest,
    LectureClarifyResponse,
    LectureCreate,
    LectureEditRequest,
    LectureEditResponse,
    LectureGenerateRequest,
    LectureResponse,
    LectureSummary,
    LectureUpdate,
)
from app.services import lecture_services
from app.services.ai_services.lecture_assistant_service import process_lecture_edit
from app.services.lecture_subjects import LECTURE_SUBJECTS, normalize_subject
from app.services.user_services import get_current_user

lecture_router = APIRouter(prefix="/lectures", tags=["lectures"])


async def get_user_from_request(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    user_dict = await get_current_user(request, db)
    result = await db.execute(select(User).where(User.id == user_dict["id"]))
    user = result.scalars().first()
    if not user:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="User not found")
    return user


@lecture_router.get("", response_model=List[LectureSummary])
async def list_lectures(
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    lectures = await lecture_services.list_lectures_for_user(user, db)
    return [lecture_services.to_summary(l) for l in lectures]


@lecture_router.get("/discover", response_model=List[LectureSummary])
async def discover_lectures(
    subject: Optional[str] = Query(
        default=None,
        description="Optional subject filter: math | science | coding | general",
    ),
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    """Published lectures from other users, optionally filtered by subject."""
    subject_key: str | None = None
    if subject and subject.strip().lower() not in ("", "all"):
        raw = subject.strip().lower()
        if raw not in LECTURE_SUBJECTS:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=400,
                detail=f"Invalid subject. Use one of: {', '.join(LECTURE_SUBJECTS)}",
            )
        subject_key = normalize_subject(raw)

    rows = await lecture_services.list_published_community_lectures(
        user, db, subject=subject_key
    )
    return [
        lecture_services.to_summary(
            lecture,
            author=lecture_services.author_label(owner),
        )
        for lecture, owner in rows
    ]


@lecture_router.post("", response_model=LectureResponse)
async def create_lecture(
    body: LectureCreate,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    lecture = await lecture_services.create_lecture(body, user, db)
    return lecture_services.to_response(lecture, viewer=user)


@lecture_router.post("/clarify", response_model=LectureClarifyResponse)
async def clarify_lecture(
    body: LectureClarifyRequest,
    user: User = Depends(get_user_from_request),
):
    """Propose short interview questions before generating a lecture."""
    _ = user
    try:
        result = await lecture_services.clarify_lecture_topic(
            body.prompt, subject=body.subject
        )
        return LectureClarifyResponse(**result)
    except Exception as exc:
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            raise
        detail = str(exc)
        if "invalid_api_key" in detail or "Incorrect API key" in detail:
            raise HTTPException(
                status_code=400,
                detail="OPENAI_API_KEY is invalid. Set a valid key in project_vl_be/.env and restart the server.",
            ) from exc
        raise HTTPException(status_code=500, detail=detail) from exc


@lecture_router.post("/generate", response_model=LectureResponse)
async def generate_lecture(
    body: LectureGenerateRequest,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    clarifications = [
        item.model_dump() if hasattr(item, "model_dump") else dict(item)
        for item in (body.clarifications or [])
    ]
    lecture = await lecture_services.generate_and_save_lecture(
        body.prompt,
        user,
        db,
        subject=body.subject,
        topic=body.topic,
        clarifications=clarifications,
    )
    return lecture_services.to_response(lecture, viewer=user)


@lecture_router.get("/{lecture_id}", response_model=LectureResponse)
async def get_lecture(
    lecture_id: uuid.UUID,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    lecture = await lecture_services.get_lecture_accessible(lecture_id, user, db)
    return lecture_services.to_response(lecture, viewer=user)


@lecture_router.patch("/{lecture_id}", response_model=LectureResponse)
async def update_lecture(
    lecture_id: uuid.UUID,
    body: LectureUpdate,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    lecture = await lecture_services.update_lecture_for_user(
        lecture_id, body, user, db
    )
    return lecture_services.to_response(lecture, viewer=user)


@lecture_router.post("/{lecture_id}/assistant", response_model=LectureEditResponse)
async def lecture_assistant(
    lecture_id: uuid.UUID,
    body: LectureEditRequest,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    lecture = await lecture_services.get_lecture_for_user(lecture_id, user, db)
    return await process_lecture_edit(
        lecture,
        body.prompt,
        user,
        db,
        draft_title=body.title,
        draft_slides=body.slides,
        current_slide=body.current_slide,
    )


@lecture_router.post("/{lecture_id}/publish", response_model=LectureResponse)
async def publish_lecture(
    lecture_id: uuid.UUID,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    lecture = await lecture_services.set_lecture_published(
        lecture_id, user, db, published=True
    )
    return lecture_services.to_response(lecture, viewer=user)


@lecture_router.post("/{lecture_id}/unpublish", response_model=LectureResponse)
async def unpublish_lecture(
    lecture_id: uuid.UUID,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    lecture = await lecture_services.set_lecture_published(
        lecture_id, user, db, published=False
    )
    return lecture_services.to_response(lecture, viewer=user)


@lecture_router.delete("/{lecture_id}")
async def delete_lecture(
    lecture_id: uuid.UUID,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    await lecture_services.delete_lecture_for_user(lecture_id, user, db)
    return {"success": True}
