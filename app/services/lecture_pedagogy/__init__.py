"""Lecture pedagogy resolver — shared arc + subject + topic packs."""

from __future__ import annotations

from app.services.lecture_pedagogy.coding import CODING_LECTURE_PEDAGOGY
from app.services.lecture_pedagogy.math_topics import (
    MATH_TOPIC_KEYWORDS,
    MATH_TOPIC_LABELS,
    MATH_TOPIC_PEDAGOGY,
)
from app.services.lecture_pedagogy.shared import LECTURE_PEDAGOGY

__all__ = [
    "CODING_LECTURE_PEDAGOGY",
    "LECTURE_PEDAGOGY",
    "MATH_TOPIC_LABELS",
    "MATH_TOPIC_PEDAGOGY",
    "infer_math_topic",
    "resolve_lecture_pedagogy",
]


def infer_math_topic(prompt: str, topic: str | None = None) -> str:
    """Return a math topic slug (algebra, trigonometry, …)."""
    if topic:
        key = topic.strip().lower().replace(" ", "_")
        aliases = {
            "trig": "trigonometry",
            "calc": "calculus",
            "calc_1": "calculus",
            "calculus_1": "calculus",
            "calculus1": "calculus",
            "afm": "functions",
            "advanced_functions": "functions",
            "function": "functions",
            "modelling": "functions",
            "modeling": "functions",
        }
        key = aliases.get(key, key)
        if key in MATH_TOPIC_PEDAGOGY:
            return key

    blob = (prompt or "").lower()
    scores: dict[str, int] = {slug: 0 for slug in MATH_TOPIC_KEYWORDS}
    for slug, words in MATH_TOPIC_KEYWORDS.items():
        for word in words:
            if word in blob:
                scores[slug] += 1
    best = max(scores, key=scores.get)
    if scores[best] <= 0:
        return "general"
    # A limit that also says "simplify" or "polynomial" is still calculus.
    if scores.get("calculus", 0) > 0 and scores["calculus"] >= scores[best]:
        return "calculus"
    return best


def resolve_lecture_pedagogy(
    *,
    subject: str,
    prompt: str,
    topic: str | None = None,
) -> tuple[str, str | None]:
    """
    Build pedagogy text for generation.

    Returns (pedagogy_block, topic_slug_or_none).
    Shared arc is always included. Topic pack is added for math (and later other subjects).
    """
    parts = [LECTURE_PEDAGOGY.strip()]
    topic_slug: str | None = None

    if subject == "math":
        topic_slug = infer_math_topic(prompt, topic)
        topic_block = MATH_TOPIC_PEDAGOGY.get(
            topic_slug, MATH_TOPIC_PEDAGOGY["general"]
        )
        parts.append(topic_block.strip())
    elif subject == "coding":
        parts.append(CODING_LECTURE_PEDAGOGY.strip())

    return "\n\n".join(parts), topic_slug
