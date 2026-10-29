from __future__ import annotations

"""Request/response models for ``POST /api/answers/``.

``AnswerRead`` mirrors the persisted ``Answer`` row: human-readable ``answer``
text, optional legacy ``blueprint``, and optional ``stage`` (``DrawingStage``
JSON for the visual engine). ``model_config.from_attributes`` allows building
from SQLAlchemy ORM instances.
"""

from datetime import datetime
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.infographics_schema import DrawingStage, InfographicBlueprint

UsageContext = Literal["personal", "hobby", "professional", "business", "education"]
SubjectDomain = Literal[
    "math",
    "science",
    "programming",
    "language",
    "history",
    "business_studies",
    "other",
]


class AnswerCreate(BaseModel):
    prompt: str = ""
    usage_context: UsageContext | None = None
    subject_domain: SubjectDomain | None = None
    equation_image: str | None = Field(
        default=None,
        description="Optional base64 data URL of a pasted math equation screenshot.",
    )
    programming_image: str | None = Field(
        default=None,
        description="Optional base64 data URL of a pasted coding-problem screenshot (LeetCode, etc.).",
    )

    @model_validator(mode="after")
    def require_prompt_or_image(self) -> AnswerCreate:
        has_prompt = bool((self.prompt or "").strip())
        has_math = bool((self.equation_image or "").strip())
        has_code = bool((self.programming_image or "").strip())
        if has_math and has_code:
            raise ValueError("Send either an equation image or a programming image, not both.")
        if not has_prompt and not has_math and not has_code:
            raise ValueError("Provide a prompt or paste a question image.")
        return self


class AnswerRead(BaseModel):
    id: UUID
    prompt: str
    answer: str
    extracted_equation: str | None = None
    extracted_kind: str | None = None
    question_type: str | None = None
    blueprint: InfographicBlueprint | None = None
    stage: DrawingStage | None = None
    created_at: datetime
    saved: bool = False

    model_config = {"from_attributes": True}


class AnswerSummary(BaseModel):
    id: UUID
    prompt: str
    title: str | None = None
    question_type: str | None = None
    created_at: datetime


class StepFollowUpRead(BaseModel):
    step_id: str
    question: str
    answer: str
    created_at: datetime


class AnswerDetail(AnswerRead):
    follow_ups: list[StepFollowUpRead] = Field(default_factory=list)


class StepFollowUpRequest(BaseModel):
    answer_id: UUID
    step_id: str
    question: str
    step_index: int
    stage: DrawingStage
    original_prompt: str | None = None


class StepFollowUpResponse(BaseModel):
    answer: str
