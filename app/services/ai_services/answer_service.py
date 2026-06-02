"""Answer generation: user question → OpenAI → ``DrawingStage`` response."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.schemas.ai_schemas.answer_schema import AnswerRead
from app.schemas.infographics_schema import DrawingStage
from app.services.ai_services.drawing_stage_objects import improve_stage_quality
from app.services.ai_services.drawing_stage_prompts import (
    build_drawing_stage_human_message,
    resolve_drawing_stage_system,
)
from app.services.ai_services.pasted_code import (
    MAX_PASTED_CODE_LINES,
    pasted_code_line_count,
)
from app.services.ai_services.question_type_identifier import identify_question_type


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
) -> AnswerRead:
    """Call the LLM with structured ``DrawingStage`` output and return ``AnswerRead``."""
    cleaned = (prompt or "").strip()
    if not cleaned:
        raise ValueError("Prompt must not be empty.")

    code_lines = pasted_code_line_count(cleaned)
    if code_lines is not None and code_lines > MAX_PASTED_CODE_LINES:
        raise ValueError(
            f"Please only provide a coding snippet with max of {MAX_PASTED_CODE_LINES} lines of code."
        )

    api_key = _openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")

    question_type = identify_question_type(
        cleaned,
        usage_context=usage_context,
        subject_domain=subject_domain,
    )

    llm = ChatOpenAI(temperature=0.2, model=_answer_model(), api_key=api_key)
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

    stage_model = await structured.ainvoke(messages)
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
        question_type=f"{question_type.domain}.{question_type.subtype}",
        blueprint=None,
        stage=stage_payload,
        created_at=datetime.now(timezone.utc),
    )
