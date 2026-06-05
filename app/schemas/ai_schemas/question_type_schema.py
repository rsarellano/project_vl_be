"""Structured output for LLM question-type routing."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QuestionTypeClassification(BaseModel):
    """Domain + subtype chosen by the classifier model."""

    domain: Literal["coding", "math", "science"]
    subtype: str = Field(
        description=(
            "Math: algebra | geometry | arithmetic | general. "
            "Coding: code_solution | code_explain | loop_trace | general. "
            "Science: biology | chemistry | physics | general."
        ),
    )
    confidence: float = Field(ge=0.0, le=1.0, default=0.85)
    rationale: str = Field(
        default="",
        description="One short sentence explaining the classification.",
    )
