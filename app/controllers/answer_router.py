"""HTTP routes for answer generation and static DrawingStage samples."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection.database import get_db
from app.schemas.ai_schemas.answer_schema import AnswerCreate, AnswerRead, StepFollowUpRequest, StepFollowUpResponse
from app.schemas.infographics_schema import DrawingStage
from app.services.ai_services.answer_service import answer_user_prompt, answer_step_follow_up
from app.services.ai_services.drawing_stage_samples import (
    get_while_loop_stage,
)

answer_router = APIRouter()


@answer_router.post("/follow-up", response_model=StepFollowUpResponse)
async def create_step_follow_up(
    data: StepFollowUpRequest, db: AsyncSession = Depends(get_db)
) -> StepFollowUpResponse:
    """Answer a user's follow-up question about a specific step."""
    try:
        answer_text = await answer_step_follow_up(data, db)
        return StepFollowUpResponse(answer=answer_text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


import json
import hashlib
from app.utils.redis_client import redis_client

from app.utils.rate_limiter import RateLimiter

@answer_router.post("/", response_model=AnswerRead, dependencies=[Depends(RateLimiter(requests=10, window=60))])
async def create_answer(data: AnswerCreate) -> AnswerRead:
    """Generate a flag-driven ``DrawingStage`` from a user prompt."""
    try:
        # Create a unique cache key based on prompt and context
        cache_key_str = f"{data.prompt}:{data.usage_context}:{data.subject_domain}"
        cache_key = f"ai_cache:{hashlib.sha256(cache_key_str.encode()).hexdigest()}"
        
        # Check Redis for cached response
        cached_response = await redis_client.get(cache_key)
        if cached_response:
            print(f"🚀 CACHE HIT! Returning instant answer from Redis for prompt: {data.prompt}")
            return AnswerRead.model_validate_json(cached_response)

        print(f"⏳ CACHE MISS! Calling OpenAI for prompt: {data.prompt}")
        # If not cached, call the actual AI service
        answer = await answer_user_prompt(
            data.prompt,
            usage_context=data.usage_context,
            subject_domain=data.subject_domain,
            equation_image=data.equation_image,
        )
        
        # Save to Redis for 24 hours (86400 seconds)
        await redis_client.setex(cache_key, 86400, answer.model_dump_json())
        
        return answer
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



