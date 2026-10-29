"""Answer generation: user question → OpenAI → ``DrawingStage`` response."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.ai_services.llm_client import build_chat_model

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_models.User import User
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
from app.services.ai_services.drawing_stage.coding.line_explain import (
    build_line_explain_stage,
)
from app.services.ai_services.pasted_code import (
    MAX_PASTED_CODE_LINES,
    MAX_WRITTEN_CODE_LINES,
    code_display_line_count,
    extract_pasted_code,
    pasted_code_line_count,
    pasted_instruction,
    subtype_for_pasted_prompt,
    user_asked_for_line_by_line,
)
from app.services.ai_services.pasted_equation_image import (
    extract_equation_from_image,
    merge_prompt_with_equation,
)
from app.services.ai_services.pasted_programming_image import (
    extract_programming_problem_from_image,
    merge_prompt_with_programming_problem,
)
from app.services.ai_services.question_title import title_from_prompt, title_from_stage
from app.services.ai_services.question_type_identifier import (
    QuestionTypeInfo,
    identify_question_type_with_llm,
)


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
        answer_snippets: list[str] = []
        other_snippets: list[str] = []
        for obj in objects:
            if not isinstance(obj, dict) or obj.get("BoxCreation") is not True:
                continue
            lines = _flatten_lines(obj.get("text"))
            if not lines:
                continue
            if obj.get("AnswerBox") is True:
                answer_snippets.append(" · ".join(lines[:3]))
            else:
                other_snippets.append(lines[0])
        if answer_snippets:
            return " → ".join(answer_snippets)
        if other_snippets:
            return " → ".join(other_snippets)

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
    programming_image: str | None = None,
    db: AsyncSession | None = None,
    user: User | None = None,
) -> AnswerRead:
    """Call the LLM with structured ``DrawingStage`` output and return ``AnswerRead``."""
    user_text = (prompt or "").strip()
    extracted_equation: str | None = None
    extracted_kind: str | None = None

    api_key = _openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")

    if programming_image and programming_image.strip():
        extracted_equation = await extract_programming_problem_from_image(
            programming_image,
            api_key=api_key,
        )
        extracted_kind = "programming"
        cleaned = merge_prompt_with_programming_problem(user_text, extracted_equation)
        subject_domain = "programming"
    elif equation_image and equation_image.strip():
        extracted_equation = await extract_equation_from_image(
            equation_image,
            api_key=api_key,
        )
        extracted_kind = "math"
        cleaned = merge_prompt_with_equation(user_text, extracted_equation)
        if not subject_domain:
            subject_domain = "math"
    else:
        cleaned = user_text

    if not cleaned:
        raise ValueError("Prompt must not be empty.")

    code_lines = pasted_code_line_count(cleaned)
    if (
        extracted_kind != "programming"
        and code_lines is not None
        and code_lines > MAX_PASTED_CODE_LINES
    ):
        raise ValueError(
            f"Please only provide a coding snippet with max of {MAX_PASTED_CODE_LINES} lines of code."
        )

    question_type = await identify_question_type_with_llm(
        cleaned,
        usage_context=usage_context,
        subject_domain=subject_domain,
        api_key=api_key,
    )
    if (
        extracted_kind == "programming"
        and question_type.subtype != "loop_trace"
    ):
        question_type = QuestionTypeInfo(
            domain="coding",
            subtype="code_solution",
            confidence=max(question_type.confidence, 0.92),
            signals=list(question_type.signals) + ["programming_image=code_solution"],
        )

    parsed_simplify = None
    if question_type.domain == "math" and question_type.subtype == "algebra":
        parsed_simplify = try_parse_simplify_prompt(cleaned)

    pasted = extract_pasted_code(cleaned)
    if pasted is not None and subtype_for_pasted_prompt(cleaned) == "code_explain":
        question_type = QuestionTypeInfo(
            domain="coding",
            subtype="code_explain",
            confidence=max(question_type.confidence, 0.95),
            signals=list(question_type.signals) + ["split=code_explain"],
        )
    if (
        question_type.domain == "coding"
        and question_type.subtype == "code_explain"
        and pasted is not None
    ):
        stage_payload = await build_line_explain_stage(
            pasted.lines,
            pasted.language,
            api_key=api_key,
            instruction=pasted_instruction(cleaned),
            line_by_line=user_asked_for_line_by_line(cleaned),
        )
    elif parsed_simplify is not None:
        stage_payload = build_simplify_expression_stage(parsed_simplify)
    else:
        llm = build_chat_model(temperature=0, model=_answer_model(), api_key=api_key)
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
    if (
        question_type.domain == "coding"
        and question_type.subtype != "code_explain"
        and code_display_line_count(stage_payload) > MAX_WRITTEN_CODE_LINES
    ):
        raise ValueError(
            "This solution is longer than 100 lines. "
            "Ask for one function, or a smaller part of the program, instead of a whole app."
        )
    answer_text = _derive_answer_text(stage_payload, prompt=cleaned)
    qtype = f"{question_type.domain}.{question_type.subtype}"

    if db is not None and user is not None:
        from app.models.ai_models.answer import Answer

        row = Answer(
            user_id=user.id,
            prompt=cleaned,
            answer=answer_text[:8000],
            blueprint=None,
            stage=stage_payload,
            question_type=qtype,
            extracted_equation=extracted_equation,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return AnswerRead(
            id=row.id,
            prompt=row.prompt,
            answer=row.answer,
            extracted_equation=row.extracted_equation,
            extracted_kind=extracted_kind,
            question_type=row.question_type,
            blueprint=None,
            stage=stage_payload,
            created_at=row.created_at,
            saved=True,
        )

    return AnswerRead(
        id=uuid4(),
        prompt=cleaned,
        answer=answer_text[:8000],
        extracted_equation=extracted_equation,
        extracted_kind=extracted_kind,
        question_type=qtype,
        blueprint=None,
        stage=stage_payload,
        created_at=datetime.now(timezone.utc),
        saved=False,
    )


from sqlalchemy import delete, select
from app.models.ai_models.answer import Answer
from app.models.ai_models.step_follow_up import StepFollowUp
from app.schemas.ai_schemas.answer_schema import (
    AnswerDetail,
    AnswerSummary,
    StepFollowUpRead,
    StepFollowUpRequest,
)
from fastapi import HTTPException

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
        "The user is asking a follow-up question about this specific diagram step/block.\n"
        "Keep your answer extremely concise, educational, and direct. "
        "For math, use plain text or LaTeX without $ delimiters when the reply is pure math. "
        "For coding, use short plain-language explanations and tiny code snippets when helpful."
    )

    history_text = ""
    if history:
        for past in history:
            history_text += f"User: {past.question}\nAssistant: {past.answer}\n\n"

    # Prefer rich context: for code-map steps, also include the source CodeDisplay.
    code_display = next(
        (
            obj
            for obj in data.stage.objects
            if getattr(obj, "CodeDisplay", False) is True
        ),
        None,
    )
    code_json = (
        code_display.model_dump_json(indent=2) if code_display is not None else "N/A"
    )

    human_content = (
        f"Original Problem: {data.original_prompt or 'N/A'}\n\n"
        f"Step Data (JSON):\n{step_json}\n\n"
        f"Code Display (JSON, if coding):\n{code_json}\n\n"
        f"Chat History:\n{history_text if history_text else 'None'}\n\n"
        f"User's new question: {data.question}"
    )

    llm = build_chat_model(temperature=0, model=_answer_model(), api_key=api_key)
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


def _stage_from_row(row: Answer) -> DrawingStage | None:
    raw = row.stage
    if not isinstance(raw, dict):
        return None
    try:
        return DrawingStage.model_validate(raw)
    except Exception:
        return None


def _answer_read_from_row(row: Answer) -> AnswerRead:
    return AnswerRead(
        id=row.id,
        prompt=row.prompt,
        answer=row.answer,
        extracted_equation=row.extracted_equation,
        question_type=row.question_type,
        blueprint=None,
        stage=_stage_from_row(row),
        created_at=row.created_at,
        saved=True,
    )


async def list_answers_for_user(
    user: User,
    db: AsyncSession,
    *,
    limit: int = 50,
) -> list[AnswerSummary]:
    stmt = (
        select(Answer)
        .where(Answer.user_id == user.id)
        .order_by(Answer.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    return [
        AnswerSummary(
            id=row.id,
            prompt=row.prompt,
            title=title_from_stage(row.stage) or title_from_prompt(row.prompt),
            question_type=row.question_type,
            created_at=row.created_at,
        )
        for row in rows
    ]


async def get_answer_for_user(
    answer_id,
    user: User,
    db: AsyncSession,
) -> AnswerDetail:
    stmt = select(Answer).where(Answer.id == answer_id, Answer.user_id == user.id)
    result = await db.execute(stmt)
    row = result.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="Saved question not found.")

    follow_stmt = (
        select(StepFollowUp)
        .where(StepFollowUp.answer_id == row.id)
        .order_by(StepFollowUp.created_at)
    )
    follow_result = await db.execute(follow_stmt)
    follow_ups = [
        StepFollowUpRead(
            step_id=item.step_id,
            question=item.question,
            answer=item.answer,
            created_at=item.created_at,
        )
        for item in follow_result.scalars().all()
    ]
    base = _answer_read_from_row(row)
    return AnswerDetail(**base.model_dump(), follow_ups=follow_ups)


async def delete_answer_for_user(
    answer_id,
    user: User,
    db: AsyncSession,
) -> None:
    """Remove one saved question (and its step follow-ups) owned by ``user``."""
    stmt = select(Answer).where(Answer.id == answer_id, Answer.user_id == user.id)
    result = await db.execute(stmt)
    row = result.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="Saved question not found.")

    await db.execute(delete(StepFollowUp).where(StepFollowUp.answer_id == row.id))
    await db.delete(row)
    await db.commit()

