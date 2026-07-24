"""Allowlisted lecture subjects — product framing + light subject guidance.

Detailed teaching rules live in ``lecture_pedagogy`` (shared arc + topic packs).
"""

from __future__ import annotations

from typing import Literal

LectureSubject = Literal["math", "science", "coding", "general"]

LECTURE_SUBJECTS: tuple[LectureSubject, ...] = ("math", "science", "coding", "general")

SUBJECT_LABELS: dict[str, str] = {
    "math": "Math",
    "science": "Science",
    "coding": "Coding",
    "general": "General",
}

# Light subject flavor only — topic pedagogy is separate (algebra vs trig, etc.).
SUBJECT_GUIDANCE: dict[str, str] = {
    "math": """
Subject focus: MATHEMATICS.
- Stay mathematical; prefer KaTeX-friendly equations (no $ delimiters, no \\text wrapping variables).
- Pick visual_type that fits the topic pack (triangle for trig, graph for functions, etc.).
""",
    "science": """
Subject focus: SCIENCE (physics, chemistry, biology, earth science).
- Explain cause/effect with a concrete real-world example on the worked_example slide.
- equation may hold a key formula or be empty if not formula-heavy.
- visual_type: prefer "equation", "graph", "circle"; "trains" only for motion/closing-speed topics.
""",
    "coding": """
Subject focus: CODING / COMPUTER SCIENCE.
- Teach with a short mental model + traced example.
- Put short code/pseudocode in equation as plain text (no markdown fences).
- visual_type: usually "equation". Do NOT invent train scenes unless the topic is literally motion/simulation.
""",
    "general": """
Subject focus: GENERAL EDUCATION.
- Teach definition → example → check → takeaway with classroom-ready language.
- visual_type: prefer "equation" unless a shape accent clearly helps.
""",
}


def normalize_subject(value: str | None) -> LectureSubject:
    raw = (value or "general").strip().lower()
    if raw in LECTURE_SUBJECTS:
        return raw  # type: ignore[return-value]
    return "general"
