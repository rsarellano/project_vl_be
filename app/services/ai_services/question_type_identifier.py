"""Keyword classifier routing prompts to drawing-stage domain modules."""

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
    """Heuristic routing — no extra LLM call. Domains: coding, math, science."""
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
    algebra_markers = ("algebra", "equation", "polynomial", "factor", "quadratic", "solve for")
    geometry_markers = ("triangle", "circle", "geometry", "angle", "area", "perimeter", "volume")
    arithmetic_markers = ("add", "subtract", "multiply", "divide", "+", "×", "percent", "fraction")
    science_markers = (
        "photosynthesis",
        "mitosis",
        "cell",
        "atom",
        "molecule",
        "force",
        "velocity",
        "energy",
        "gravity",
        "chemical",
        "reaction",
        "acid",
        "base",
        "biology",
        "chemistry",
        "physics",
        "experiment",
        "hypothesis",
        "ecosystem",
        "dna",
        "organism",
    )

    coding_score = sum(1 for marker in coding_markers if marker in text)
    algebra_score = sum(1 for marker in algebra_markers if marker in text)
    geometry_score = sum(1 for marker in geometry_markers if marker in text)
    arithmetic_score = sum(1 for marker in arithmetic_markers if marker in text)
    science_score = sum(1 for marker in science_markers if marker in text)
    math_score = algebra_score + geometry_score + arithmetic_score

    if subject_domain == "programming":
        coding_score += 3
    if subject_domain == "math":
        math_score += 3
        algebra_score += 1
    if subject_domain == "science":
        science_score += 3

    if (
        coding_score >= max(math_score, science_score, 2)
        or looks_like_pasted_code(prompt)
        or looks_like_coding_request(prompt)
    ):
        pasted_code = looks_like_pasted_code(prompt)
        explicit_loop_trace_keywords = (
            "trace the loop",
            "trace this loop",
            "trace loop",
            "each iteration",
            "iteration by iteration",
            "step through",
            "walk through the loop",
            "what does this loop do",
        )
        has_explicit_loop_trace_intent = any(
            keyword in text for keyword in explicit_loop_trace_keywords
        ) or ("trace" in text and "loop" in text)
        mentions_loop_construct = "for loop" in text or "while loop" in text
        is_loop_trace = has_explicit_loop_trace_intent or (
            mentions_loop_construct and not pasted_code
        )

        if pasted_code and not user_asked_to_implement(prompt):
            subtype = "code_explain"
        elif is_loop_trace:
            subtype = "loop_trace"
        else:
            subtype = "code_solution"
        confidence = min(
            0.98,
            0.45 + max(coding_score, 3 if pasted_code else 0) * 0.1,
        )
        loop_signals = [f"coding_score={coding_score}", f"loop_trace={is_loop_trace}"]
        if pasted_code:
            loop_signals.append("pasted_code")
        if looks_like_coding_request(prompt):
            loop_signals.append("coding_request")
        return QuestionTypeInfo(
            domain="coding",
            subtype=subtype,
            confidence=confidence,
            signals=signals + loop_signals,
        )

    if science_score >= max(math_score, 2) and science_score >= 2:
        subtype = "general"
        if any(m in text for m in ("force", "velocity", "energy", "gravity", "motion", "newton")):
            subtype = "physics"
        elif any(m in text for m in ("reaction", "acid", "base", "molecule", "compound", "bond")):
            subtype = "chemistry"
        elif any(m in text for m in ("cell", "dna", "organism", "mitosis", "photosynthesis", "ecosystem")):
            subtype = "biology"
        return QuestionTypeInfo(
            domain="science",
            subtype=subtype,
            confidence=min(0.9, 0.4 + science_score * 0.1),
            signals=signals + [f"science_score={science_score}", f"subtype={subtype}"],
        )

    if algebra_score >= geometry_score and algebra_score >= arithmetic_score and algebra_score >= 2:
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

    if arithmetic_score >= 2 or math_score >= 2:
        return QuestionTypeInfo(
            domain="math",
            subtype="arithmetic",
            confidence=min(0.85, 0.35 + math_score * 0.1),
            signals=signals + [f"math_score={math_score}"],
        )

    if subject_domain == "science":
        return QuestionTypeInfo(
            domain="science",
            subtype="general",
            confidence=0.55,
            signals=signals + ["subject_domain_science_fallback"],
        )

    if subject_domain == "math":
        return QuestionTypeInfo(
            domain="math",
            subtype="general",
            confidence=0.55,
            signals=signals + ["subject_domain_math_fallback"],
        )

    return QuestionTypeInfo(
        domain="math",
        subtype="general",
        confidence=0.35,
        signals=signals + ["fallback=math_general"],
    )
