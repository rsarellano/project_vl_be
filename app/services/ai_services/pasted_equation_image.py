"""Read math equations from pasted images via a vision model."""

from __future__ import annotations

import os
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

_MAX_IMAGE_DATA_URL_LEN = 4_000_000

_EQUATION_OCR_SYSTEM = """\
You extract math equations from images for a visual learning app.
Return exactly one equation or expression in plain text on a single line.

Rules:
- Prefer LaTeX for roots: \\sqrt{2x+5} - x = 1 (not sqrt(...)).
- Use standard operators: + - * / = and parentheses.
- Preserve variables (x, y, m, n, etc.) exactly as shown.
- Do not add words like "Solve" — only the math.
- If multiple lines exist, return the main equation only.
- If no math is visible, return an empty equation field.
"""

_WHITESPACE = re.compile(r"\s+")


class EquationOcrResult(BaseModel):
    equation: str = Field(
        description="The equation or expression read from the image, plain text.",
    )


def _vision_model() -> str:
    return os.getenv("OPENAI_VISION_MODEL", os.getenv("OPENAI_ANSWER_MODEL", "gpt-4o"))


def normalize_image_data_url(value: str) -> str:
    """Accept a data URL or raw base64 and return a vision-ready data URL."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError("Equation image is empty.")
    if len(cleaned) > _MAX_IMAGE_DATA_URL_LEN:
        raise ValueError("Equation image is too large. Paste a smaller screenshot.")
    if cleaned.startswith("data:"):
        if not cleaned.startswith("data:image/"):
            raise ValueError("Only image files are supported for equation paste.")
        return cleaned
    return f"data:image/png;base64,{cleaned}"


def normalize_equation_text(equation: str) -> str:
    text = _WHITESPACE.sub(" ", (equation or "").strip())
    text = text.strip("`\"'")
    return text


def merge_prompt_with_equation(user_text: str, equation: str) -> str:
    """Combine optional user instructions with OCR'd equation text."""
    eq = normalize_equation_text(equation)
    if not eq:
        raise ValueError("Could not read an equation from the pasted image.")
    text = (user_text or "").strip()
    if not text:
        if "=" in eq:
            return f"Solve the equation: {eq}"
        return f"Simplify the expression: {eq}"
    return f"{text}\n\nEquation from image: {eq}"


async def extract_equation_from_image(image_data_url: str, *, api_key: str) -> str:
    """OCR a math equation from a base64 data URL using a vision-capable model."""
    data_url = normalize_image_data_url(image_data_url)

    llm = ChatOpenAI(
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
        ],
    )
    if result is None:
        raise ValueError("Could not read an equation from the pasted image.")

    equation = normalize_equation_text(result.equation)
    if not equation:
        raise ValueError("Could not read an equation from the pasted image.")
    return equation
