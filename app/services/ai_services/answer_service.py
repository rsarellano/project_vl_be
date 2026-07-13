"""Answer generation: user question → OpenAI → ``DrawingStage`` response."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from pydantic import ValidationError

from app.schemas.ai_schemas.answer_schema import AnswerRead
from app.schemas.infographics_schema import DrawingStage
from app.services.ai_services.drawing_stage_errors import friendly_diagram_generation_error
from app.services.ai_services.drawing_stage_objects import improve_stage_quality
from app.services.ai_services.drawing_stage.math.algebra_simplify import (
    build_simplify_expression_stage,
    try_parse_simplify_prompt,
)
from app.services.ai_services.drawing_stage_prompts import (
    build_drawing_stage_human_message,
    resolve_drawing_stage_system,
)
from app.services.ai_services.pasted_code import (
    MAX_PASTED_CODE_LINES,
    pasted_code_line_count,
)
from app.services.ai_services.pasted_equation_image import (
    extract_equation_from_image,
    merge_prompt_with_equation,
)
from app.services.ai_services.question_type_identifier import identify_question_type_with_llm


def _openai_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY")


def _answer_model() -> str:
    return os.getenv("OPENAI_ANSWER_MODEL", "gpt-4o")


def _flatten_lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _derive_answer_text(stage_payload: dict[str, Any], *, prompt: str) -> str:
    """Build persisted preview text from flag-driven box content."""
    objects = stage_payload.get("objects") if isinstance(stage_payload, dict) else None
    if isinstance(objects, list):
        snippets: list[str] = []
        for obj in objects:
            if not isinstance(obj, dict) or obj.get("BoxCreation") is not True:
                continue
            lines = _flatten_lines(obj.get("text"))
            if lines:
                snippets.append(lines[0])
        if snippets:
            return " → ".join(snippets)

    cleaned = (prompt or "").strip()
    if cleaned:
        return f"Diagram generated for: {cleaned[:180]}"
    return "Generated diagram."


async def answer_user_prompt(
    prompt: str,
    *,
    usage_context: str | None = None,
    subject_domain: str | None = None,
    equation_image: str | None = None,
) -> AnswerRead:
    """Call the LLM with structured ``DrawingStage`` output and return ``AnswerRead``."""
    user_text = (prompt or "").strip()
    extracted_equation: str | None = None

    api_key = _openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")

    if equation_image and equation_image.strip():
        extracted_equation = await extract_equation_from_image(
            equation_image,
            api_key=api_key,
        )
        cleaned = merge_prompt_with_equation(user_text, extracted_equation)
    else:
        cleaned = user_text

    if not cleaned:
        raise ValueError("Prompt must not be empty.")

    code_lines = pasted_code_line_count(cleaned)
    if code_lines is not None and code_lines > MAX_PASTED_CODE_LINES:
        raise ValueError(
            f"Please only provide a coding snippet with max of {MAX_PASTED_CODE_LINES} lines of code."
        )

    question_type = await identify_question_type_with_llm(
        cleaned,
        usage_context=usage_context,
        subject_domain=subject_domain,
        api_key=api_key,
    )

    parsed_simplify = None
    if question_type.domain == "math" and question_type.subtype == "algebra":
        parsed_simplify = try_parse_simplify_prompt(cleaned)

    if parsed_simplify is not None:
        stage_payload = build_simplify_expression_stage(parsed_simplify)
    else:
        llm = ChatOpenAI(temperature=0, model=_answer_model(), api_key=api_key)
        structured = llm.with_structured_output(DrawingStage, method="function_calling")

        messages = [
            SystemMessage(content=resolve_drawing_stage_system(question_type)),
            HumanMessage(
                content=build_drawing_stage_human_message(
                    cleaned,
                    question_type,
                    usage_context=usage_context,
                ),
            ),
        ]

        try:
            stage_model = await structured.ainvoke(messages)
        except ValidationError as exc:
            raise ValueError(
                friendly_diagram_generation_error(
                    domain=question_type.domain,
                    subtype=question_type.subtype,
                )
            ) from exc
        except Exception as exc:
            if "validation error" in str(exc).lower():
                raise ValueError(
                    friendly_diagram_generation_error(
                        domain=question_type.domain,
                        subtype=question_type.subtype,
                    )
                ) from exc
            raise

        if stage_model is None:
            raise ValueError("Model did not return valid drawing stage: empty result")

        stage_payload = stage_model.model_dump(mode="json", by_alias=True)
    stage_payload = improve_stage_quality(
        stage_payload,
        domain=question_type.domain,
        prompt=cleaned,
    )
    answer_text = _derive_answer_text(stage_payload, prompt=cleaned)

    return AnswerRead(
        id=uuid4(),
        prompt=cleaned,
        answer=answer_text[:8000],
        extracted_equation=extracted_equation,
        question_type=f"{question_type.domain}.{question_type.subtype}",
        blueprint=None,
        stage=stage_payload,
        created_at=datetime.now(timezone.utc),
    )


import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ai_models.step_follow_up import StepFollowUp
from app.schemas.ai_schemas.answer_schema import StepFollowUpRequest

async def answer_step_follow_up(data: StepFollowUpRequest, db: AsyncSession) -> str:
    api_key = _openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")

    # Fetch chat history for this step
    stmt = select(StepFollowUp).where(
        StepFollowUp.answer_id == data.answer_id,
        StepFollowUp.step_id == data.step_id
    ).order_by(StepFollowUp.created_at)
    result = await db.execute(stmt)
    history = result.scalars().all()

    # Extract the step data to give to the LLM
    step_data = next((obj for obj in data.stage.objects if str(obj.id) == data.step_id), None)
    step_json = step_data.model_dump_json(indent=2) if step_data else "Step data not found."

    system_prompt = (
        "You are an expert AI tutor explaining a specific step in a math or coding problem.\n"
        "The user is asking a follow-up question about this specific step in the derivation.\n"
        "Keep your answer extremely concise, educational, and direct. Use plain text or LaTeX (without $ delimiters if it's pure math)."
    )

    history_text = ""
    if history:
        for past in history:
            history_text += f"User: {past.question}\nAssistant: {past.answer}\n\n"

    human_content = (
        f"Original Problem: {data.original_prompt or 'N/A'}\n\n"
        f"Step Data (JSON):\n{step_json}\n\n"
        f"Chat History:\n{history_text if history else 'None'}\n\n"
        f"User's new question: {data.question}"
    )

    llm = ChatOpenAI(temperature=0, model=_answer_model(), api_key=api_key)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content),
    ]

    response = await llm.ainvoke(messages)
    answer_text = str(response.content)

    # Save to DB
    new_follow_up = StepFollowUp(
        answer_id=data.answer_id,
        step_id=data.step_id,
        question=data.question,
        answer=answer_text
    )
    db.add(new_follow_up)
    await db.commit()

    return answer_text

