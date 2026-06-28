"""Shared helpers for domain-specific drawing-stage prompts."""

from __future__ import annotations

from app.services.ai_services.pasted_code import extract_pasted_code
from app.services.ai_services.question_type_identifier import QuestionTypeInfo

CANVAS_WIDTH = 1400
CANVAS_HEIGHT = 1250
CANVAS_BACKGROUND = "#ffffff"

OUTPUT_FORMAT_CLOSING = (
    "Return ONLY one raw JSON object (no markdown, no commentary), then stop "
    "immediately after the closing brace."
)

TRUNK_FORBIDDEN_ITEM_KEYS = (
    "``type``, ``x``, ``y``, ``width``, ``height``, ``radius``, ``fill``, "
    "``stroke``, ``strokeWidth``, ``padding``, ``fontSize``, ``lineHeight``, "
    "``textColor``, ``fontWeight``, ``textAnchor``, ``points``, ``animation``"
)

TRUNK_FORBIDDEN_TOP_LEVEL = (
    "``lines``, ``layoutHint``, ``explanation``, ``narrationBeats``"
)


def build_usage_context_guidance(usage_context: str | None) -> str:
    if not usage_context:
        return ""
    guides = {
        "personal": (
            "Audience: personal learner. Use approachable tone, everyday examples, "
            "and practical takeaways without jargon."
        ),
        "hobby": (
            "Audience: hobby learner. Keep it engaging and exploratory; use relatable "
            "examples from creative or leisure interests without sounding like homework."
        ),
        "professional": (
            "Audience: professional. Prefer workplace scenarios, concise steps, "
            "and skills applicable on the job."
        ),
        "business": (
            "Audience: business context. Emphasize processes, stakeholders, metrics, "
            "and decisions relevant to teams or operations."
        ),
        "education": (
            "Audience: student or classroom. Use curriculum-friendly language, "
            "scaffold from basics, and highlight what to remember for assessments."
        ),
    }
    line = guides.get((usage_context or "").strip().lower())
    if not line:
        return ""
    return f"Usage context: {usage_context}.\n{line}"


def build_pasted_code_block(prompt: str) -> str:
    """Coding only — spell out CodeDisplay.text when user pasted source."""
    pasted = extract_pasted_code(prompt)
    if not pasted:
        return ""

    body = "\n".join(pasted.lines)
    return (
        "USER-SUPPLIED SOURCE CODE (mandatory — reproduce exactly in CodeDisplay.text, "
        "one array element per line below; do NOT substitute unrelated code such as "
        "findMax, twoSum, or other tutorial examples):\n"
        f"Suggested language: {pasted.language}\n"
        "---\n"
        f"{body}\n"
        "---\n\n"
    )


def classifier_header(question_type: QuestionTypeInfo) -> str:
    return (
        f"Classifier domain={question_type.domain}, subtype={question_type.subtype}, "
        f"confidence={question_type.confidence:.2f}, "
        f"signals={', '.join(question_type.signals)}.\n"
    )
