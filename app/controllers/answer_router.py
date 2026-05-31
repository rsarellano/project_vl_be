"""HTTP routes for answer generation and static DrawingStage samples."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.ai_schemas.answer_schema import AnswerCreate, AnswerRead
from app.schemas.infographics_schema import DrawingStage
from app.services.ai_services.answer_service import answer_user_prompt
from app.services.ai_services.drawing_stage_samples import (
    get_two_sum_code_map_stage,
    get_while_loop_stage,
)

answer_router = APIRouter()


@answer_router.post("/", response_model=AnswerRead)
async def create_answer(data: AnswerCreate) -> AnswerRead:
    """Generate a flag-driven ``DrawingStage`` from a user prompt."""
    try:
        return await answer_user_prompt(
            data.prompt,
            usage_context=data.usage_context,
            subject_domain=data.subject_domain,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@answer_router.get("/samples/while-loop", response_model=DrawingStage)
async def sample_while_loop_stage() -> DrawingStage:
    """Static trunk ``DrawingStage`` tracing ``while (i < 3)`` (no LLM)."""
    return get_while_loop_stage()


@answer_router.get("/samples/two-sum", response_model=DrawingStage)
async def sample_two_sum_code_map_stage() -> DrawingStage:
    """Static ``DrawingStage`` for Two Sum in code-map layout (no LLM)."""
    return get_two_sum_code_map_stage()
