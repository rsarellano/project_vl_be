"""Read math equations from pasted images via a vision model."""

from __future__ import annotations

import os
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.ai_services.llm_client import build_chat_model
from pydantic import BaseModel, Field

from app.services.ai_services.pasted_image_data import normalize_image_data_url

_EQUATION_OCR_SYSTEM = """\
You extract math equations from images for a visual learning app.
Return exactly one equation or expression in plain text on a single line.

Rules:
- Prefer LaTeX for roots: \\sqrt{2x+5} - x = 1 (not sqrt(...)).
- Limits: \\lim_{x \\to 3} (x^2 + 5x - 4). Derivatives: \\frac{d}{dx}(x^3) or f'(x).
- Use standard operators: + - * / = and plain parentheses ( ).
- Never wrap the answer in math delimiters: no \\( \\), \\[ \\], or $ signs.
- Preserve variables (x, y, m, n, etc.) exactly as shown.
- Do not add words like "Solve" — only the math.
- If multiple lines exist, return the main equation only.
- If no math is visible, return an empty equation field.
"""

_WHITESPACE = re.compile(r"\s+")
_MATH_DELIMITERS = re.compile(r"\\[\(\)\[\]]|\$+")
_LIMIT_HINT = re.compile(r"\\lim\b|\blim\b|x\s*(?:->|→|\\to)", re.IGNORECASE)
_DERIVATIVE_HINT = re.compile(
    r"\\frac\{d\}\{d[a-z]\}|\bd/d[a-z]\b|\bd[a-z]/d[a-z]\b|[a-zA-Z]\s*'\s*\(|derivative",
    re.IGNORECASE,
)


class EquationOcrResult(BaseModel):
    equation: str = Field(
        description="The equation or expression read from the image, plain text.",
    )


def _vision_model() -> str:
    return os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")


def normalize_equation_text(equation: str) -> str:
    text = (equation or "").strip()
    # OCR models often wrap parts in \( \) or $ — those break KaTeX downstream.
    text = _MATH_DELIMITERS.sub(lambda m: "(" if m.group(0) == "\\(" else ")" if m.group(0) == "\\)" else "", text)
    text = _WHITESPACE.sub(" ", text).strip()
    text = text.strip("`\"'")
    return text


def default_instruction_for_equation(equation: str) -> str:
    """Pick the task wording that matches the math read from the image."""
    eq = equation or ""
    if _LIMIT_HINT.search(eq):
        return "Evaluate the limit"
    if _DERIVATIVE_HINT.search(eq):
        return "Find the derivative"
    if "=" in eq:
        return "Solve the equation"
    return "Simplify the expression"


def merge_prompt_with_equation(user_text: str, equation: str) -> str:
    """Combine optional user instructions with OCR'd equation text."""
    eq = normalize_equation_text(equation)
    if not eq:
        raise ValueError("Could not read an equation from the pasted image.")
    text = (user_text or "").strip()
    if not text:
        return f"{default_instruction_for_equation(eq)}: {eq}"
    return f"{text}\n\nEquation from image: {eq}"


async def extract_equation_from_image(image_data_url: str, *, api_key: str) -> str:
    """OCR a math equation from a base64 data URL using a vision-capable model."""
    data_url = normalize_image_data_url(image_data_url)

    llm = build_chat_model(
        temperature=0,
        model=_vision_model(),
        api_key=api_key,
    )
    structured = llm.with_structured_output(EquationOcrResult, method="function_calling")
    result = await structured.ainvoke(
        [
            SystemMessage(content=_EQUATION_OCR_SYSTEM),
            HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": "Read the math equation or expression in this image.",
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            ),
        ]
    )
    if result is None:
        raise ValueError("Could not read an equation from the pasted image.")

    equation = normalize_equation_text(result.equation)
    if not equation:
        raise ValueError("Could not read an equation from the pasted image.")
    return equation
