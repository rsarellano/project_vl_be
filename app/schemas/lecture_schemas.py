"""Pydantic schemas for lecture CRUD + AI generate."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


SceneArchetype = Literal[
    "math_worked_example",
    "math_graph",
    "math_geometry",
    "code_walkthrough",
    "code_flow",
    "science_process",
    "science_force_vector",
    "relative_motion_trains",
    "concept_comparison",
    "basic_boxes",
]


class LectureSceneHint(BaseModel):
    """Semantic scene instructions selected by AI; builders own all geometry."""

    archetype: SceneArchetype = "basic_boxes"
    focus: str = Field(default="", max_length=180)
    concepts: list[str] = Field(default_factory=list, max_length=4)
    code_language: str | None = Field(default=None, max_length=40)
    variables: dict[str, str] = Field(default_factory=dict)
    motion: str | None = Field(default=None, max_length=80)
    emphasis: str | None = Field(default=None, max_length=180)


class LectureCheckpointChoice(BaseModel):
    id: str = Field(default="a", max_length=40)
    text: str = Field(default="", max_length=400)
    correct: bool = False


class LectureCheckpoint(BaseModel):
    """Soft-gate question students attempt before the next slide."""

    prompt: str = Field(default="", max_length=800)
    kind: Literal["multiple_choice", "numeric"] = "multiple_choice"
    choices: list[LectureCheckpointChoice] = Field(default_factory=list, max_length=6)
    numericAnswer: str = Field(default="", max_length=80)
    explanation: str = Field(default="", max_length=800)


class LectureSlide(BaseModel):
    number: int = 1
    title: str = ""
    equation: str = ""
    narration: str = ""
    explanation: str = ""
    visual_type: str = "equation"
    slide_role: str = "concept"
    callout: str = ""
    steps: list[str] = Field(default_factory=list)
    # AI chooses semantic intent only. ``lecture_scene.py`` materializes the scene.
    scene_hint: LectureSceneHint | None = None
    scene: Optional[dict[str, Any]] = None
    # Coding slides may include optional source lines used by code walkthrough builders.
    code_lines: list[str] = Field(default_factory=list)
    code_portions: list[dict[str, Any]] = Field(default_factory=list)
    checkpoint: LectureCheckpoint | None = None


class LectureCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    slides: list[LectureSlide] = Field(default_factory=list)
    prompt: Optional[str] = None
    subject: str = "general"


class LectureClarifyOption(BaseModel):
    id: str = Field(max_length=40)
    label: str = Field(max_length=160)


class LectureClarifyQuestion(BaseModel):
    id: str = Field(max_length=40)
    prompt: str = Field(max_length=280)
    options: list[LectureClarifyOption] = Field(default_factory=list, max_length=6)


class LectureClarifyRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    subject: str = Field(default="math", description="math | science | coding | general")


class LectureClarifyResponse(BaseModel):
    topic_summary: str = ""
    questions: list[LectureClarifyQuestion] = Field(default_factory=list)


class LectureClarificationAnswer(BaseModel):
    question_id: str = Field(max_length=40)
    question: str = Field(max_length=280)
    answer: str = Field(min_length=1, max_length=500)


class LectureGenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    subject: str = Field(default="math", description="math | science | coding | general")
    topic: str | None = Field(
        default=None,
        description="Optional math topic pack: algebra | trigonometry | geometry | functions | calculus",
    )
    clarifications: list[LectureClarificationAnswer] = Field(
        default_factory=list,
        description="Answers from the pre-generate interview",
    )


class LectureUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    slides: Optional[list[LectureSlide]] = None
    subject: Optional[str] = None


class LectureResponse(BaseModel):
    id: UUID
    title: str
    subject: str = "general"
    prompt: Optional[str] = None
    slides: list[dict[str, Any]] = Field(default_factory=list)
    is_published: bool = False
    published_at: Optional[datetime] = None
    is_owner: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LectureSummary(BaseModel):
    id: UUID
    title: str
    subject: str = "general"
    slide_count: int
    is_published: bool = False
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # Present on community / discover listings (email local-part).
    author: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LectureEditRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    # Optional unsaved editor draft — AI uses this as the working lecture instead of DB-only.
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    slides: Optional[list[LectureSlide]] = None
    current_slide: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-based slide the educator is currently viewing (for 'this slide')",
    )


class LectureEditResponse(BaseModel):
    message: str
    lecture: Optional[LectureResponse] = None
    # Technical changelog for auditing — not shown in the educator UI by default.
    details: list[str] = Field(default_factory=list)
