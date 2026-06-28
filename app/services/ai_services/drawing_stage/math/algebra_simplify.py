"""Deterministic diagram builder for \"simplify expression\" algebra prompts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.services.ai_services.drawing_stage.shared import (
    CANVAS_BACKGROUND,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
)

_VARIABLE_TERM = re.compile(r"\d+\s*[a-zA-Z]|[a-zA-Z]\s*[\+\-\*\/]|\b[a-zA-Z]\s*\d")
_EXPRESSION_AFTER_KEYWORD = re.compile(
    r"expression\s+([0-9a-zA-Z\+\-\.\s]+)",
    re.IGNORECASE,
)
_MATH_FRAGMENT = re.compile(r"[\d\.]*[a-zA-Z][\d\+\-\.\s]*|[\d\+\-\.\s]+[a-zA-Z][\d\+\-\.\s]*")


@dataclass(frozen=True)
class ParsedSimplifyExpression:
    raw: str
    variable: str
    variable_terms: tuple[str, ...]
    constants: tuple[str, ...]
    combined_variable: str
    combined_constant: int
    simplified: str


def looks_like_simplify_expression(prompt: str) -> bool:
    text = (prompt or "").strip().lower()
    return "simplify" in text and bool(_VARIABLE_TERM.search(text))


def _extract_expression(prompt: str) -> str | None:
    match = _EXPRESSION_AFTER_KEYWORD.search(prompt)
    if match:
        return re.sub(r"\s+", "", match.group(1).strip())
    fragments = _MATH_FRAGMENT.findall(prompt)
    if not fragments:
        return None
    best = max(fragments, key=len)
    cleaned = re.sub(r"\s+", "", best)
    return cleaned if _VARIABLE_TERM.search(cleaned) else None


def _split_additive_terms(expr: str) -> list[str]:
    normalized = re.sub(r"\s+", "", expr)
    if not normalized:
        return []
    parts = re.split(r"(?=[\+\-])", normalized)
    return [part for part in parts if part]


def _term_variable(term: str) -> str | None:
    match = re.search(r"[a-zA-Z]+", term)
    return match.group(0) if match else None


def _parse_simplify_expression(expr: str) -> ParsedSimplifyExpression | None:
    terms = _split_additive_terms(expr)
    if not terms:
        return None

    variable: str | None = None
    variable_terms: list[str] = []
    constants: list[str] = []

    for term in terms:
        var = _term_variable(term)
        if var:
            if variable is None:
                variable = var
            elif variable != var:
                return None
            variable_terms.append(term)
        elif re.fullmatch(r"[\+\-]?\d+\.?\d*", term):
            constants.append(term)
        else:
            return None

    if not variable or not variable_terms:
        return None

    var_sum = _sum_variable_terms(variable_terms, variable)
    const_sum = _sum_constants(constants)
    simplified = _format_simplified(var_sum, const_sum)

    return ParsedSimplifyExpression(
        raw=expr,
        variable=variable,
        variable_terms=tuple(variable_terms),
        constants=tuple(constants),
        combined_variable=var_sum,
        combined_constant=const_sum,
        simplified=simplified,
    )


def _sum_variable_terms(terms: list[str], variable: str) -> str:
    total = 0
    for term in terms:
        body = term
        sign = 1
        if body.startswith("+"):
            body = body[1:]
        elif body.startswith("-"):
            sign = -1
            body = body[1:]
        coef_match = re.fullmatch(rf"(\d*){re.escape(variable)}", body)
        if not coef_match:
            continue
        coef_str = coef_match.group(1)
        coef = int(coef_str) if coef_str else 1
        total += sign * coef

    if total == 0:
        return "0"
    if total == 1:
        return variable
    if total == -1:
        return f"-{variable}"
    return f"{total}{variable}"


def _sum_constants(terms: list[str]) -> int:
    total = 0
    for term in terms:
        total += int(term)
    return total


def _format_simplified(var_part: str, const_sum: int) -> str:
    if var_part == "0":
        return str(const_sum)
    if const_sum == 0:
        return var_part
    sign = "+" if const_sum > 0 else "-"
    magnitude = abs(const_sum)
    return f"{var_part} {sign} {magnitude}"


def _strip_leading_plus(term: str) -> str:
    return term[1:] if term.startswith("+") else term


def _format_term_list(terms: tuple[str, ...]) -> str:
    return ", ".join(_strip_leading_plus(term) for term in terms)


def _format_variable_work(terms: tuple[str, ...], combined: str) -> str:
    if len(terms) <= 1:
        return combined
    parts: list[str] = []
    for index, term in enumerate(terms):
        body = _strip_leading_plus(term)
        if index == 0:
            parts.append(body)
        elif body.startswith("-"):
            parts.append(f"- {body[1:]}")
        else:
            parts.append(f"+ {body}")
    return f"{' '.join(parts)} = {combined}"


def _format_constant_work(constants: tuple[str, ...], total: int) -> str:
    if not constants:
        return str(total)
    if len(constants) == 1:
        return f"{_strip_leading_plus(constants[0])} = {total}"
    parts: list[str] = []
    for index, term in enumerate(constants):
        value = int(term)
        if index == 0:
            parts.append(str(value))
        elif value >= 0:
            parts.append(f"+ {value}")
        else:
            parts.append(f"- {abs(value)}")
    return f"{' '.join(parts)} = {total}"


def _format_display_expression(expr: str) -> str:
    terms = _split_additive_terms(expr)
    if not terms:
        return expr
    parts: list[str] = []
    for index, term in enumerate(terms):
        if index == 0:
            parts.append(term)
            continue
        if term.startswith("+"):
            parts.append(f" + {term[1:]}")
        else:
            parts.append(f" {term}")
    return "".join(parts)


def try_parse_simplify_prompt(prompt: str) -> ParsedSimplifyExpression | None:
    if not looks_like_simplify_expression(prompt):
        return None
    expr = _extract_expression(prompt)
    if not expr:
        return None
    return _parse_simplify_expression(expr)


def _build_variable_terms_derivation(
    variable: str,
    variable_terms: tuple[str, ...],
    combined_variable: str,
    from_step_id: str,
) -> dict[str, Any]:
    work = _format_variable_work(variable_terms, combined_variable)
    lhs = work.split("=", 1)[0].strip()
    return {
        "fromStepId": from_step_id,
        "beats": [
            {"type": "note", "text": f"Combine the {variable} terms on the left."},
            {"type": "expression", "text": lhs, "id": "f1"},
            {"type": "arrow", "direction": "down"},
            {
                "type": "explain",
                "text": (
                    f"Like terms share the same variable ({variable}). "
                    "We add their coefficients — the numbers in front."
                ),
            },
            {
                "type": "explain",
                "text": (
                    f"Adding the coefficients gives {combined_variable}. "
                    "Only the number in front changes; the variable stays the same."
                ),
            },
            {"type": "arrow", "direction": "down"},
            {"type": "note", "text": f"Result: {combined_variable}"},
            {"type": "expression", "text": combined_variable, "id": "f2"},
        ],
    }


def build_simplify_expression_stage(parsed: ParsedSimplifyExpression) -> dict[str, Any]:
    """Build a complete DrawingStage for a parseable simplify-expression prompt."""
    title = _format_display_expression(parsed.raw)
    var_label = f"{parsed.variable} terms"
    var_list = _format_term_list(parsed.variable_terms)
    combined = parsed.simplified
    var_work = _format_variable_work(parsed.variable_terms, parsed.combined_variable)

    step_one_lines = ["Group like terms", "", f"{var_label}: {var_list}"]
    if parsed.constants:
        step_one_lines.append(f"constants: {_format_term_list(parsed.constants)}")

    boxes: list[dict[str, Any]] = [
        {"id": "step-1", "BoxCreation": True, "text": step_one_lines},
    ]
    step_id = 2

    if len(parsed.variable_terms) > 1:
        prev_id = boxes[-1]["id"]
        boxes.append(
            {
                "id": f"step-{step_id}",
                "BoxCreation": True,
                "text": [f"Combine {parsed.variable} terms", "", var_work],
                "derivation": _build_variable_terms_derivation(
                    parsed.variable,
                    parsed.variable_terms,
                    parsed.combined_variable,
                    str(prev_id),
                ),
            }
        )
        step_id += 1

    if len(parsed.constants) > 1:
        const_work = _format_constant_work(parsed.constants, parsed.combined_constant)
        boxes.append(
            {
                "id": f"step-{step_id}",
                "BoxCreation": True,
                "text": ["Combine constants", "", const_work],
            }
        )
        step_id += 1

    if parsed.constants:
        boxes.append(
            {
                "id": f"step-{step_id}",
                "BoxCreation": True,
                "text": ["Put groups together", "", combined],
            }
        )

    boxes.append(
        {"id": "result", "BoxCreation": True, "text": ["Simplified Expression", "", combined]},
    )

    connections: list[dict[str, Any]] = []
    box_ids = [box["id"] for box in boxes]
    for left, right in zip(box_ids, box_ids[1:], strict=False):
        connections.append({"LineCreation": True, "from": left, "to": right})

    return {
        "width": CANVAS_WIDTH,
        "height": CANVAS_HEIGHT,
        "background": CANVAS_BACKGROUND,
        "layoutMode": "math",
        "objects": [
            {
                "id": "problem",
                "TextCreation": True,
                "role": "code-title",
                "text": [title],
            },
            {
                "id": "objective",
                "TextCreation": True,
                "role": "objective",
                "text": ["Objective:", "Simplify the expression"],
            },
            *boxes,
        ],
        "connections": connections,
    }
