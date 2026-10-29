"""HTTP routes for answer generation and static DrawingStage samples."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.connection.database import get_db
from app.models.user_models.User import User
from app.schemas.ai_schemas.answer_schema import (
    AnswerCreate,
    AnswerDetail,
    AnswerRead,
    AnswerSummary,
    StepFollowUpRequest,
    StepFollowUpResponse,
)
from app.schemas.infographics_schema import DrawingStage
from app.services.ai_services.answer_service import (
    answer_step_follow_up,
    answer_user_prompt,
    delete_answer_for_user,
    get_answer_for_user,
    list_answers_for_user,
)
from app.services.ai_services.drawing_stage_samples import get_while_loop_stage
from app.services.user_services import get_current_user

answer_router = APIRouter()


async def get_user_from_request(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    user_dict = await get_current_user(request, db)
    result = await db.execute(select(User).where(User.id == user_dict["id"]))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_optional_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User | None:
    if not request.cookies.get("token"):
        return None
    try:
        return await get_user_from_request(request, db)
    except HTTPException:
        return None


@answer_router.post("/", response_model=AnswerRead)
async def create_answer(
    data: AnswerCreate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> AnswerRead:
    """Generate a flag-driven ``DrawingStage`` from a user prompt."""
    try:
        return await answer_user_prompt(
            data.prompt,
            usage_context=data.usage_context,
            subject_domain=data.subject_domain,
            equation_image=data.equation_image,
            programming_image=data.programming_image,
            db=db,
            user=user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        detail = str(exc)
        if "invalid_api_key" in detail or "Incorrect API key" in detail:
            raise HTTPException(
                status_code=400,
                detail="OPENAI_API_KEY is invalid. Set a valid key in project_vl_be/.env and restart the server.",
            ) from exc
        raise HTTPException(status_code=500, detail=detail) from exc


@answer_router.get("/", response_model=list[AnswerSummary])
async def list_answers(
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
) -> list[AnswerSummary]:
    return await list_answers_for_user(user, db)


@answer_router.get("/{answer_id}", response_model=AnswerDetail)
async def get_answer(
    answer_id: uuid.UUID,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
) -> AnswerDetail:
    return await get_answer_for_user(answer_id, user, db)


@answer_router.delete("/{answer_id}", status_code=204)
async def delete_answer(
    answer_id: uuid.UUID,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove a saved question from the user's list."""
    await delete_answer_for_user(answer_id, user, db)
    return Response(status_code=204)


@answer_router.post("/follow-up", response_model=StepFollowUpResponse)
async def create_step_follow_up(
    data: StepFollowUpRequest,
    db: AsyncSession = Depends(get_db),
) -> StepFollowUpResponse:
    """Answer a follow-up question about one math/coding diagram step."""
    try:
        answer = await answer_step_follow_up(data, db)
        return StepFollowUpResponse(answer=answer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        detail = str(exc)
        if "invalid_api_key" in detail or "Incorrect API key" in detail:
            raise HTTPException(
                status_code=400,
                detail="OPENAI_API_KEY is invalid. Set a valid key in project_vl_be/.env and restart the server.",
            ) from exc
        raise HTTPException(status_code=500, detail=detail) from exc


@answer_router.get("/samples/while-loop", response_model=DrawingStage)
async def sample_while_loop_stage() -> DrawingStage:
    """Static trunk ``DrawingStage`` tracing ``while (i < 3)`` (no LLM)."""
    return get_while_loop_stage()
