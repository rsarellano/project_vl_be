from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExamQuestion(BaseModel):
    id: str
    number: int
    prompt: str
    topic: str | None = None
    difficulty: str | None = None
    question_type: Literal["short_answer", "multiple_choice"] = "short_answer"
    choices: list[str] | None = None
    correct_answer: str


class GeneratedExam(BaseModel):
    """Structured exam stored in ``Assignment.stage_data``."""

    type: Literal["exam"] = "exam"
    title: str
    questions: list[ExamQuestion] = Field(min_length=1)
    generated_at: str


class ExamQuestionStudentView(BaseModel):
    id: str
    number: int
    prompt: str
    topic: str | None = None
    difficulty: str | None = None
    question_type: Literal["short_answer", "multiple_choice"] = "short_answer"
    choices: list[str] | None = None


class ExamStudentView(BaseModel):
    type: Literal["exam"] = "exam"
    title: str
    questions: list[ExamQuestionStudentView]


class SubmissionCreate(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


class SubmissionResponse(BaseModel):
    id: UUID
    assignment_id: UUID
    student_id: UUID
    answers: dict[str, str]
    submitted_at: datetime
    score: float | None = None

    model_config = ConfigDict(from_attributes=True)


class AssignmentDetailResponse(BaseModel):
    id: UUID
    classroom_id: UUID
    prompt: str
    stage_data: dict[str, Any]
    submission: SubmissionResponse | None = None

    model_config = ConfigDict(from_attributes=True)
