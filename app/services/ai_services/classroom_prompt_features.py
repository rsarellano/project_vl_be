"""Features an educator may ask for in a classroom create or edit prompt.

Anything outside this list is refused. The assistant message points back at the list.
"""

from __future__ import annotations

import re
from typing import Any, Literal

PromptKind = Literal["create", "classroom"]

CREATE_FEATURES: tuple[str, ...] = (
    "Classroom name",
    "Description",
    "Grading policy",
    "How many students can join",
    "Who can take tests: every enrolled student, or an allowlist",
    "Whether new students are added to that allowlist automatically",
)

CLASSROOM_FEATURES: tuple[str, ...] = (
    *CREATE_FEATURES,
    "Rename the classroom",
    "Create, edit, or delete a quiz, exam, test, or lecture (saved as an assignment)",
    "How many questions to include, for example 10",
    "Short-answer questions (the student types a text answer)",
    "Multiple-choice questions, with choices and one correct answer",
    "A topic and difficulty on a question",
    "Who can take one specific assignment",
    "Add current members, newcomers, or named students to an allowlist",
)

# Student activities this product cannot collect on an assignment.
_UNSUPPORTED_ACTIVITY = re.compile(
    r"("
    r"\b(?:must|have to|needs? to|should|will)\s+(?:draw|sketch|hand[\s-]?write|label)\b"
    r"|\b(?:draw|sketch)\s+(?:on|onto)\b"
    r"|\b(?:draw|sketch|hand[\s-]?write|label)\s+(?:the\s+|a\s+|an\s+)?(?:diagram|figure|picture|image|shape|graph|triangle)\b"
    r"|\bdrawing\s+(?:question|activity|task|response|answer)\b"
    r"|\b(?:students?|users?|they|learners?)\b.{0,40}\b(?:draw|sketch)\b"
    r"|\blabel\s+(?:the\s+|a\s+)?(?:diagram|figure|picture|image)\b"
    r"|\bupload\s+(?:a\s+|an\s+)?(?:file|image|photo|picture)\b"
    r"|\b(?:voice|audio|video)\s+answer\b"
    r"|\brecord\s+(?:a\s+|an\s+)?(?:video|audio)\b"
    r"|\bdrag and drop\b"
    r"|\bhotspot\b"
    r")",
    re.IGNORECASE,
)

_ALLOWED_QUESTION_TYPES = {"short_answer", "multiple_choice"}


def features_for(kind: PromptKind) -> tuple[str, ...]:
    return CREATE_FEATURES if kind == "create" else CLASSROOM_FEATURES


def feature_list_text(kind: PromptKind) -> str:
    return "\n".join(f"- {item}" for item in features_for(kind))


def feature_guide(kind: PromptKind) -> str:
    where = (
        "when creating a classroom"
        if kind == "create"
        else "when creating or changing a classroom"
    )
    extra = ""
    if kind == "create":
        extra = (
            "\n\nQuizzes and questions are added after you open the classroom, "
            "not in this create prompt."
        )
    return (
        "That is not something this prompt can set up. "
        f"Ask only for features {where}:\n"
        f"{feature_list_text(kind)}"
        f"{extra}"
    )


def prompt_feature_rules(kind: PromptKind) -> str:
    return f"""Allowed features only
You may fulfill ONLY the features on this list:
{feature_list_text(kind)}

If any part of the request needs something that is not on the list, set unsupported_request to true.
Do not invent a substitute. In particular, never turn a drawing, sketch, diagram-label, file-upload, audio, or video task into a typed question.
- Do the parts that are on the list.
- Leave the unsupported part undone.
- If nothing on the list can satisfy the request, use only "no_action".
- In "message", say what you could not do and that they should use the feature list.
Examples that are allowed: "create 10 short-answer questions", "multiple choice quiz on algebra", "limit the class to 15 students".
Examples that are not allowed: "a question students have to draw", "upload a photo of their work", "label this diagram"."""


_TEXT_QUESTION_REQUEST = re.compile(
    r"\b(\d+\s+questions?|short[\s-]?answer|multiple[\s-]?choice)\b",
    re.IGNORECASE,
)


def mentions_unsupported_activity(prompt: str) -> bool:
    return bool(_UNSUPPORTED_ACTIVITY.search(prompt or ""))


_ASSIGNMENT_ASK = re.compile(
    r"\b(\d+\s+questions?|(?:a|an)\s+(?:quiz|exam|assignment)|questions?\s+(?:on|about)|multiple[\s-]?choice|short[\s-]?answer)\b",
    re.IGNORECASE,
)
_CREATE_CLASSROOM = re.compile(
    r"\b(create|make|add|new)\b.{0,40}\b(classroom|class)\b",
    re.IGNORECASE,
)


def asks_for_assignment_content(prompt: str) -> bool:
    return bool(_ASSIGNMENT_ASK.search(prompt or ""))


def asks_to_create_classroom(prompt: str) -> bool:
    return bool(_CREATE_CLASSROOM.search(prompt or ""))


def keep_assignment_edits(prompt: str) -> bool:
    """A drawing-only request must not become a typed quiz."""
    if not mentions_unsupported_activity(prompt):
        return True
    return bool(_TEXT_QUESTION_REQUEST.search(prompt or ""))


def sanitize_questions(raw: Any) -> tuple[list[dict[str, Any]], int]:
    """Keep only short-answer and multiple-choice questions. Returns (kept, dropped)."""
    if not isinstance(raw, list):
        return [], 0
    kept: list[dict[str, Any]] = []
    dropped = 0
    for item in raw:
        if not isinstance(item, dict):
            dropped += 1
            continue
        question_type = str(item.get("question_type") or "short_answer").strip()
        prompt = str(item.get("prompt") or "")
        if question_type not in _ALLOWED_QUESTION_TYPES or _UNSUPPORTED_ACTIVITY.search(prompt):
            dropped += 1
            continue
        kept.append(item)
    return kept, dropped


def with_feature_guide(message: str, kind: PromptKind) -> str:
    guide = feature_guide(kind)
    text = (message or "").strip()
    if "Ask only for features" in text:
        return text
    if not text:
        return guide
    return f"{text}\n\n{guide}"
