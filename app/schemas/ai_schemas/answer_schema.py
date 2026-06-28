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
        description="Optional base64 data URL of a pasted equation image.",
    )

    @model_validator(mode="after")
    def require_prompt_or_image(self) -> AnswerCreate:
        has_prompt = bool((self.prompt or "").strip())
        has_image = bool((self.equation_image or "").strip())
        if not has_prompt and not has_image:
            raise ValueError("Provide a prompt or paste an equation image.")
        return self


class AnswerRead(BaseModel):
    id: UUID
    prompt: str
    answer: str
    extracted_equation: str | None = None
    question_type: str | None = None
    blueprint: InfographicBlueprint | None = None
    stage: DrawingStage | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
