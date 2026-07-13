"""Generate classroom exams from educator meta-prompts via structured LLM output."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.schemas.classroom_schemas.exam_schemas import ExamQuestion, GeneratedExam

EXAM_SYSTEM_PROMPT = """\
You create classroom exams for educators.

Given a meta-prompt (e.g. "create 5 intermediate algebra questions"), produce a \
complete exam with that many questions.

Rules:
- Match the requested count, subject, and difficulty when specified.
- Each question must be solvable on its own with a clear correct_answer.
- Prefer short_answer unless multiple_choice is clearly better (then provide 4 choices).
- Use plain text math notation (x^2, sqrt(x), fractions like 3/4) — no LaTeX delimiters.
- Number questions starting at 1.
- Do not repeat questions.
- Keep prompts concise and appropriate for the stated level.
"""


class _ExamQuestionDraft(BaseModel):
    prompt: str
    topic: str | None = None
    difficulty: str | None = None
    question_type: str = "short_answer"
    choices: list[str] | None = None
    correct_answer: str


class _ExamDraft(BaseModel):
    title: str
    questions: list[_ExamQuestionDraft] = Field(min_length=1)


def _openai_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY")


def _exam_model() -> str:
    return os.getenv("OPENAI_EXAM_MODEL", os.getenv("OPENAI_ANSWER_MODEL", "gpt-4o-mini"))


async def generate_exam_from_prompt(meta_prompt: str) -> GeneratedExam:
    cleaned = (meta_prompt or "").strip()
    if not cleaned:
        raise ValueError("Exam prompt must not be empty.")

    api_key = _openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")

    llm = ChatOpenAI(temperature=0.4, model=_exam_model(), api_key=api_key)
    structured = llm.with_structured_output(_ExamDraft, method="function_calling")

    draft: _ExamDraft = await structured.ainvoke(
        [
            SystemMessage(content=EXAM_SYSTEM_PROMPT),
            HumanMessage(content=cleaned),
        ]
    )

    questions: list[ExamQuestion] = []
    for index, item in enumerate(draft.questions, start=1):
        q_type = item.question_type if item.question_type in ("short_answer", "multiple_choice") else "short_answer"
        choices = item.choices if q_type == "multiple_choice" else None
        if q_type == "multiple_choice" and (not choices or len(choices) < 2):
            q_type = "short_answer"
            choices = None

        questions.append(
            ExamQuestion(
                id=str(uuid4()),
                number=index,
                prompt=item.prompt.strip(),
                topic=(item.topic or "").strip() or None,
                difficulty=(item.difficulty or "").strip() or None,
                question_type=q_type,
                choices=choices,
                correct_answer=item.correct_answer.strip(),
            )
        )

    return GeneratedExam(
        title=draft.title.strip() or "Generated Exam",
        questions=questions,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
