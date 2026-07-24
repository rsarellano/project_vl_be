"""Lecture library API — persist AI-generated and manual lectures."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.connection.database import get_db
from app.models.user_models.User import User
from app.schemas.lecture_schemas import (
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


@lecture_router.post("", response_model=LectureResponse)
async def create_lecture(
    body: LectureCreate,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    lecture = await lecture_services.create_lecture(body, user, db)
    return lecture_services.to_response(lecture, viewer=user)


@lecture_router.post("/generate", response_model=LectureResponse)
async def generate_lecture(
    body: LectureGenerateRequest,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    lecture = await lecture_services.generate_and_save_lecture(
        body.prompt, user, db, subject=body.subject, topic=body.topic
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
