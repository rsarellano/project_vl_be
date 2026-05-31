"""Keyword classifier routing prompts to drawing-stage system variants."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.ai_services.pasted_code import (
    looks_like_coding_request,
    looks_like_pasted_code,
    user_asked_to_implement,
)


@dataclass(frozen=True)
class QuestionTypeInfo:
    domain: str
    subtype: str
    confidence: float
    signals: list[str]


def identify_question_type(
    prompt: str,
    *,
    usage_context: str | None = None,
    subject_domain: str | None = None,
) -> QuestionTypeInfo:
    """Heuristic routing — no extra LLM call."""
    text = (prompt or "").strip().lower()
    signals: list[str] = []

    if subject_domain:
        signals.append(f"subject_domain={subject_domain}")
    if usage_context:
        signals.append(f"usage_context={usage_context}")

    coding_markers = (
        "javascript",
        "typescript",
        "python",
        "java",
        "function",
        "algorithm",
        "leetcode",
        "array",
        "loop",
        "while",
        "for ",
        "console.log",
        "code",
        "def ",
        "const ",
        "class ",
        "two sum",
        " in js",
        "sample",
    )
    algebra_markers = ("algebra", "equation", "polynomial", "factor", "quadratic")
    geometry_markers = ("triangle", "circle", "geometry", "angle", "area", "perimeter")

    coding_score = sum(1 for marker in coding_markers if marker in text)
    algebra_score = sum(1 for marker in algebra_markers if marker in text)
    geometry_score = sum(1 for marker in geometry_markers if marker in text)

    if subject_domain == "programming":
        coding_score += 3

    if (
        coding_score >= max(algebra_score, geometry_score, 2)
        or looks_like_pasted_code(prompt)
        or looks_like_coding_request(prompt)
    ):
        loop_trace_keywords = (
            "for loop",
            "while loop",
            "trace the loop",
            "each iteration",
            "console.log",
            "what does this loop",
            "iteration by iteration",
            "step through",
        )
        is_loop_trace = any(k in text for k in loop_trace_keywords) or (
            "trace" in text and "loop" in text
        )
        if is_loop_trace:
            subtype = "loop_trace"
        elif looks_like_pasted_code(prompt) and not user_asked_to_implement(prompt):
            subtype = "code_explain"
        else:
            subtype = "code_solution"
        confidence = min(
            0.98,
            0.45 + max(coding_score, 3 if looks_like_pasted_code(prompt) else 0) * 0.1,
        )
        loop_signals = [f"coding_score={coding_score}", f"loop_trace={is_loop_trace}"]
        if looks_like_pasted_code(prompt):
            loop_signals.append("pasted_code")
        if looks_like_coding_request(prompt):
            loop_signals.append("coding_request")
        return QuestionTypeInfo(
            domain="coding",
            subtype=subtype,
            confidence=confidence,
            signals=signals + loop_signals,
        )

    if algebra_score >= geometry_score and algebra_score >= 2:
        return QuestionTypeInfo(
            domain="math",
            subtype="algebra",
            confidence=min(0.9, 0.4 + algebra_score * 0.1),
            signals=signals + [f"algebra_score={algebra_score}"],
        )

    if geometry_score >= 2:
        return QuestionTypeInfo(
            domain="math",
            subtype="geometry",
            confidence=min(0.9, 0.4 + geometry_score * 0.1),
            signals=signals + [f"geometry_score={geometry_score}"],
        )

    return QuestionTypeInfo(
        domain="general",
        subtype="general",
        confidence=0.35,
        signals=signals + ["fallback=general"],
    )
