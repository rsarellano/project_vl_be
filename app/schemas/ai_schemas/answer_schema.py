"""Request/response models for ``POST /api/answers/``.

``AnswerRead`` mirrors the persisted ``Answer`` row: human-readable ``answer``
text, optional legacy ``blueprint``, and optional ``stage`` (``DrawingStage``
JSON for the visual engine). ``model_config.from_attributes`` allows building
from SQLAlchemy ORM instances.
"""

from datetime import datetime
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.infographics_schema import DrawingStage, InfographicBlueprint

UsageContext = Literal["personal", "professional", "business", "education"]
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
    prompt: str = Field(..., min_length=1)
    usage_context: UsageContext | None = None
    subject_domain: SubjectDomain | None = None


class AnswerRead(BaseModel):
    id: UUID
    prompt: str
    answer: str
    question_type: str | None = None
    blueprint: InfographicBlueprint | None = None
    stage: DrawingStage | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
