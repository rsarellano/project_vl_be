"""Question-type routing — LLM classifier with keyword heuristic fallback."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.ai_services.llm_client import build_chat_model

from app.schemas.ai_schemas.question_type_schema import QuestionTypeClassification
from app.services.ai_services.pasted_code import (
    looks_like_coding_request,
    looks_like_pasted_code,
    looks_like_problem_statement,
    subtype_for_pasted_prompt,
    user_asked_to_implement,
)

_VARIABLE_TERM = re.compile(r"\d+\s*[a-zA-Z]|[a-zA-Z]\s*[\+\-\*\/]|\b[a-zA-Z]\s*\d")

# Limits and derivatives must win over the algebra bonus that a lone "x" receives.
_CALCULUS_HINT = re.compile(
    r"("
    r"\b(?:calculus|derivative|derivatives|differentiate|differentiation|"
    r"d/dx|dy/dx|continuity|power rule|product rule|quotient rule|chain rule|"
    r"tangent line|instantaneous rate)\b"
    r"|\blim(?:it)?\b"
    r"|f\s*'\s*\("
    r"|x\s*(?:->|→)"
    r")",
    re.IGNORECASE,
)


def looks_like_calculus(prompt: str) -> bool:
    return bool(_CALCULUS_HINT.search(prompt or ""))

_VALID_SUBTYPES: dict[str, frozenset[str]] = {
    "math": frozenset({"algebra", "geometry", "arithmetic", "trigonometry", "calculus", "general"}),
    "coding": frozenset({"code_solution", "code_explain", "loop_trace", "general"}),
    "science": frozenset({"biology", "chemistry", "physics", "general"}),
}

_CLASSIFIER_SYSTEM = """\
You classify user prompts for a visual learning diagram engine.
Return exactly one domain and subtype.

Domains and subtypes:
- math.calculus — Calculus 1: limits, continuity, derivatives, and tangent lines. \
Example: "lim x->3 of x^2+5x-4" and "derivative of x^3" are calculus, even though they contain x.
- math.algebra — equations, solving for variables, simplifying expressions with variables \
(like terms), factoring, symbolic manipulation. Example: "Simplify 4m+5+2m-1" is algebra.
- math.trigonometry — right-triangle problems using sin/cos/tan (SOH CAH TOA), finding \
missing sides or angles, inverse trig (arcsin/arccos/arctan). Example: "Find the opposite \
side of a right triangle with hypotenuse 10 and angle 30°" is trigonometry. \
Derivative of sin(x) is calculus, not trigonometry.
- math.geometry — shapes, area, perimeter, volume, angles, coordinates, proofs about figures \
(NOT trigonometry — use math.trigonometry for sin/cos/tan problems).
- math.arithmetic — numeric computation only (no variables): fractions, percents, order of \
operations, word problems with pure numbers.
- math.general — other math not clearly algebra/geometry/arithmetic/trigonometry/calculus.
- coding.code_explain — user pasted existing source code to understand (explain this code).
- coding.loop_trace — trace a loop iteration-by-iteration.
- coding.code_solution — implement/write/solve a programming problem, including \
LeetCode-style statements with examples but no source code.
- coding.general — other programming topics.
- science.biology | science.chemistry | science.physics | science.general.

Rules:
- Limits (lim, x->a), derivatives (d/dx, f'), continuity, and tangent lines → math.calculus, \
NOT algebra, even when the expression contains x or the word simplify.
- Expressions with variables (x, m, n, etc.) to simplify or rewrite → math.algebra, NOT arithmetic.
- "Solve for x" or equations → math.algebra.
- Problems mentioning sin, cos, tan, hypotenuse, opposite, adjacent, SOH CAH TOA → math.trigonometry, NOT geometry.
- Only classify as arithmetic when the task is numeric with no variables.
- Prefer the most specific subtype; use "general" only when unclear.
"""


@dataclass(frozen=True)
class QuestionTypeInfo:
    domain: str
    subtype: str
    confidence: float
    signals: list[str]


def _classifier_model() -> str:
    return os.getenv("OPENAI_CLASSIFIER_MODEL", "gpt-4o-mini")


def _normalize_subtype(domain: str, subtype: str) -> str:
    allowed = _VALID_SUBTYPES.get(domain)
    if not allowed:
        return "general"
    cleaned = (subtype or "").strip().lower().replace("-", "_")
    if cleaned in allowed:
        return cleaned
    return "general"


def _coding_paste_override(prompt: str) -> QuestionTypeInfo | None:
    """High-confidence routing from the split question, not from words inside the code."""
    subtype = subtype_for_pasted_prompt(prompt)
    if subtype is None:
        return None
    if subtype == "code_solution" and not (
        looks_like_pasted_code(prompt) or looks_like_problem_statement(prompt)
    ):
        return None
    return QuestionTypeInfo(
        domain="coding",
        subtype=subtype,
        confidence=0.95,
        signals=["classifier=paste_override", f"subtype={subtype}"],
    )


def identify_question_type_heuristic(
    prompt: str,
    *,
    usage_context: str | None = None,
    subject_domain: str | None = None,
) -> QuestionTypeInfo:
    """Keyword routing fallback — no LLM call."""
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
    calculus_markers = (
        "calculus",
        "derivative",
        "differentiate",
        "differentiation",
        "d/dx",
        "dy/dx",
        "continuity",
        "tangent line",
        "power rule",
        "product rule",
        "quotient rule",
        "chain rule",
    )
    trigonometry_markers = (
        "sin", "cos", "tan", "sine", "cosine", "tangent",
        "hypotenuse", "opposite side", "adjacent side",
        "soh cah toa", "sohcahtoa", "right triangle angle",
        "arcsin", "arccos", "arctan", "inverse trig",
        "trigonometry", "trig",
    )
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
    calculus_score = sum(1 for marker in calculus_markers if marker in text)
    if looks_like_calculus(text):
        calculus_score += 4
        signals.append("calculus_hint")
    if _VARIABLE_TERM.search(text):
        algebra_score += 3
        signals.append("variable_terms")
    trigonometry_score = sum(1 for marker in trigonometry_markers if marker in text)
    geometry_score = sum(1 for marker in geometry_markers if marker in text)
    arithmetic_score = sum(1 for marker in arithmetic_markers if marker in text)
    science_score = sum(1 for marker in science_markers if marker in text)
    math_score = (
        algebra_score + geometry_score + arithmetic_score + trigonometry_score + calculus_score
    )

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

        pasted_subtype = subtype_for_pasted_prompt(prompt)
        if pasted_subtype is not None:
            subtype = pasted_subtype
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

    # Calculus before algebra: "lim x->3 (x^2+5x-4)" contains x but is not a simplify task.
    # Also before trigonometry: "derivative of sin(x)" is calculus.
    if calculus_score >= 1:
        return QuestionTypeInfo(
            domain="math",
            subtype="calculus",
            confidence=min(0.95, 0.82 + calculus_score * 0.04),
            signals=signals + [f"calculus_score={calculus_score}"],
        )

    # Trigonometry must be checked BEFORE geometry (trig problems mention "triangle" / "angle")
    if trigonometry_score >= 2:
        return QuestionTypeInfo(
            domain="math",
            subtype="trigonometry",
            confidence=min(0.9, 0.4 + trigonometry_score * 0.1),
            signals=signals + [f"trigonometry_score={trigonometry_score}"],
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


def identify_question_type(
    prompt: str,
    *,
    usage_context: str | None = None,
    subject_domain: str | None = None,
) -> QuestionTypeInfo:
    """Sync entry — heuristic only (tests and LLM fallback)."""
    return identify_question_type_heuristic(
        prompt,
        usage_context=usage_context,
        subject_domain=subject_domain,
    )


async def identify_question_type_with_llm(
    prompt: str,
    *,
    usage_context: str | None = None,
    subject_domain: str | None = None,
    api_key: str,
) -> QuestionTypeInfo:
    """LLM classifier with paste override and keyword fallback."""
    cleaned = (prompt or "").strip()
    base_signals: list[str] = []
    if subject_domain:
        base_signals.append(f"subject_domain={subject_domain}")
    if usage_context:
        base_signals.append(f"usage_context={usage_context}")

    paste_override = _coding_paste_override(cleaned)
    if paste_override:
        return QuestionTypeInfo(
            domain=paste_override.domain,
            subtype=paste_override.subtype,
            confidence=paste_override.confidence,
            signals=base_signals + paste_override.signals,
        )

    heuristic = identify_question_type_heuristic(
        cleaned,
        usage_context=usage_context,
        subject_domain=subject_domain,
    )
    if heuristic.confidence >= 0.85:
        return heuristic

    user_lines = [f"User prompt: {cleaned}"]
    if subject_domain:
        user_lines.append(f"Learner subject preference: {subject_domain}")
    if usage_context:
        user_lines.append(f"Usage context: {usage_context}")

    try:
        llm = build_chat_model(
            temperature=0,
            model=_classifier_model(),
            api_key=api_key,
        )
        structured = llm.with_structured_output(
            QuestionTypeClassification,
            method="function_calling",
        )
        result = await structured.ainvoke(
            [
                SystemMessage(content=_CLASSIFIER_SYSTEM),
                HumanMessage(content="\n".join(user_lines)),
            ],
        )
        if result is None:
            raise ValueError("Classifier returned empty result")

        domain = result.domain
        subtype = _normalize_subtype(domain, result.subtype)
        if looks_like_calculus(cleaned):
            domain = "math"
            subtype = "calculus"
            signals_note = "calculus_override"
        else:
            signals_note = None
        rationale = (result.rationale or "").strip()
        signals = base_signals + ["classifier=llm", f"subtype={subtype}"]
        if signals_note:
            signals.append(signals_note)
        if rationale:
            signals.append(f"rationale={rationale[:120]}")

        return QuestionTypeInfo(
            domain=domain,
            subtype=subtype,
            confidence=float(result.confidence),
            signals=signals,
        )
    except Exception as exc:
        return QuestionTypeInfo(
            domain=heuristic.domain,
            subtype=heuristic.subtype,
            confidence=heuristic.confidence,
            signals=base_signals + heuristic.signals + [f"classifier=heuristic_fallback", f"error={exc}"],
        )
