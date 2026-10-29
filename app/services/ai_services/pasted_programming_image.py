"""Read coding/LeetCode problems from pasted screenshots via a vision model."""

from __future__ import annotations

import os
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.ai_services.llm_client import build_chat_model
from pydantic import BaseModel, Field

from app.services.ai_services.pasted_image_data import normalize_image_data_url

_PROGRAMMING_OCR_SYSTEM = """\
You extract coding problems from screenshots (LeetCode, HackerRank, interview prompts, homework).

Return the full problem in plain text:
- Title, statement, examples (input / output / explanation), complexity, constraints.
- Keep array and code examples exactly (e.g. nums1 = [1,3]).
- Skip site chrome: Easy/Hard, Topics, Companies, nav, ads, likes.
- Do not solve the problem. Do not invent missing parts.
- If this is not a programming problem, return an empty problem field.
"""

_LEFTOVER_MATH = re.compile(
    r"(solve the equation|simplify the expression|\\sqrt|√|[a-zA-Z]\s*=\s*|=\s*\d)",
    re.IGNORECASE,
)
_CODING_HINT = re.compile(
    r"\b(leetcode|array|nums|function|algorithm|python|javascript|hash\s*map)\b",
    re.IGNORECASE,
)


class ProgrammingOcrResult(BaseModel):
    problem: str = Field(
        description="Full programming problem statement from the screenshot, or empty if none.",
    )


def _vision_model() -> str:
    return os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")


def normalize_problem_text(text: str) -> str:
    return (text or "").strip().strip("`\"'")


def _looks_like_leftover_math_prompt(user_text: str) -> bool:
    text = (user_text or "").strip()
    if not text:
        return True
    if _CODING_HINT.search(text):
        return False
    if len(text) > 180:
        return False
    return bool(_LEFTOVER_MATH.search(text))


def merge_prompt_with_programming_problem(user_text: str, problem: str) -> str:
    """Turn OCR'd coding-problem text into the tutor prompt."""
    body = normalize_problem_text(problem)
    if not body:
        raise ValueError("Could not read a programming problem from the pasted image.")
    extra = (user_text or "").strip()
    if not extra or _looks_like_leftover_math_prompt(extra):
        return (
            "Explain and walk through this programming problem visually, then give "
            "a working solution.\n\n"
            "IMPORTANT:\n"
            "- CodeDisplay.text must be complete runnable solution code of at most 100 lines "
            "(core solution only) — NEVER dump "
            "this problem statement into the code panel.\n"
            "- Add one BoxCreation with AnswerBox: true (no linkedPortion) whose text "
            "is the answer: first-example result plus time complexity "
            "(e.g. \"Example 1 → 2.0\" / \"O(log(m+n))\").\n\n"
            f"{body}"
        )
    return (
        f"{extra}\n\nProblem from image:\n{body}\n\n"
        "CodeDisplay.text = working solution code, not the problem text. "
        "Include BoxCreation AnswerBox: true at the bottom with the example result "
        "and complexity."
    )


async def extract_programming_problem_from_image(
    image_data_url: str,
    *,
    api_key: str,
) -> str:
    """OCR a coding problem from a pasted screenshot."""
    data_url = normalize_image_data_url(image_data_url)

    llm = build_chat_model(
        temperature=0,
        model=_vision_model(),
        api_key=api_key,
    )
    structured = llm.with_structured_output(
        ProgrammingOcrResult,
        method="function_calling",
    )
    result = await structured.ainvoke(
        [
            SystemMessage(content=_PROGRAMMING_OCR_SYSTEM),
            HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": "Read the programming problem in this screenshot.",
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            ),
        ]
    )
    if result is None:
        raise ValueError("Could not read a programming problem from the pasted image.")

    problem = normalize_problem_text(result.problem)
    if not problem:
        raise ValueError("Could not read a programming problem from the pasted image.")
    return problem
