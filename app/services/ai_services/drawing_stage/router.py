"""Route (domain, subtype) to a single focused prompt module."""

from __future__ import annotations

from app.services.ai_services.drawing_stage.math.algebra_simplify import looks_like_simplify_expression
from app.services.ai_services.pasted_code import extract_pasted_code
from app.services.ai_services.question_type_identifier import QuestionTypeInfo

from .registry import get_subtype_prompt
from .shared import (
    OUTPUT_FORMAT_CLOSING,
    build_pasted_code_block,
    build_usage_context_guidance,
    classifier_header,
)


def resolve_drawing_stage_system(question_type: QuestionTypeInfo) -> str:
    return get_subtype_prompt(question_type).system


def build_drawing_stage_human_message(
    prompt: str,
    question_type: QuestionTypeInfo,
    *,
    usage_context: str | None = None,
) -> str:
    spec = get_subtype_prompt(question_type)
    p = (prompt or "").strip() or "(no topic — choose a classic walkthrough)"
    usage_block = build_usage_context_guidance(usage_context)
    usage_prefix = f"{usage_block}\n\n" if usage_block else ""

    pasted_block = ""
    if spec.domain == "coding":
        pasted_block = build_pasted_code_block(p)

    produce = spec.produce_line
    if not produce and spec.domain == "coding":
        produce = (
            f'Produce code-map DrawingStage (layoutMode="code-map"). '
            f"Subtype={spec.subtype}."
        )
    elif not produce:
        produce = f'Produce DrawingStage (layoutMode="{spec.layout_mode}").'

    hint = spec.human_hint
    if (
        spec.domain == "math"
        and spec.subtype == "algebra"
        and looks_like_simplify_expression(p)
    ):
        hint = (
            "This is a simplify-expression task. Box 1 lists all groups. Then separate boxes: "
            "combine variable terms (show arithmetic, e.g. 4x + 2x = 6x), combine constants "
            "(show arithmetic, e.g. 5 - 1 = 4), put groups together, then simplified form.\n\n"
            f"{hint}"
        )
    hint_block = f"{hint}\n\n" if hint else ""

    return (
        f"User message (must drive the topic when valid): {p}\n\n"
        f"{pasted_block}"
        f"{usage_prefix}"
        f"{classifier_header(question_type)}"
        f"{hint_block}"
        f"{produce} {OUTPUT_FORMAT_CLOSING}"
    )
