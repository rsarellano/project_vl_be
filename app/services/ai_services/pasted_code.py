"""Detect and extract source code pasted into the user's prompt."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PastedCode:
    lines: list[str]
    language: str


_IMPLEMENT_KEYWORDS = (
    "implement ",
    "write a function",
    "write a program",
    "write code",
    "solve ",
    "leetcode",
    "create a function",
    "create a sample",
    "create sample",
    "build a function",
    "how do i solve",
    "complete the function",
    "sample implementation",
    "show me how to code",
    "generate code",
)

_CODING_LANGUAGE_HINTS = (
    " javascript",
    " typescript",
    " python",
    " java",
    " c++",
    " golang",
    " rust",
    " in js",
    " in ts",
    " in py",
    " in python",
    " in javascript",
    " in typescript",
)

_ALGO_HINTS = (
    "two sum",
    "binary search",
    "linked list",
    "hash map",
    "dynamic programming",
    "fibonacci",
    "bubble sort",
    "merge sort",
    "reverse string",
    "palindrome",
    "valid parentheses",
    "max subarray",
)

_CODE_LINE_MARKERS = (
    "export ",
    "import ",
    "interface ",
    "class ",
    "function ",
    "const ",
    "let ",
    "var ",
    "def ",
    "public ",
    "private ",
    "protected ",
    "type ",
    "enum ",
    "struct ",
    "return ",
    "if ",
    "for ",
    "while ",
    "extends ",
    "implements ",
)


def user_asked_to_implement(prompt: str) -> bool:
    """True when the user wants a new solution written, not an explanation of pasted code."""
    text = (prompt or "").strip().lower()
    return any(keyword in text for keyword in _IMPLEMENT_KEYWORDS)


def looks_like_coding_request(prompt: str) -> bool:
    """True when the user wants a code explanation or solution (not math trunk layout)."""
    text = (prompt or "").strip()
    if not text:
        return False
    if looks_like_pasted_code(text):
        return True

    lower = text.lower()
    if any(hint in lower for hint in _CODING_LANGUAGE_HINTS):
        return True
    if any(hint in lower for hint in _ALGO_HINTS):
        return True
    if re.search(r"\b(js|ts|tsx|jsx|py)\b", lower):
        return True

    coding_verbs = (
        "code",
        "function",
        "program",
        "algorithm",
        "leetcode",
        "javascript",
        "python",
        "typescript",
        "console.log",
    )
    has_coding_verb = any(verb in lower for verb in coding_verbs)

    if user_asked_to_implement(text) and has_coding_verb:
        return True
    if user_asked_to_implement(text) and any(hint in lower for hint in _ALGO_HINTS):
        return True
    if any(
        phrase in lower
        for phrase in ("create a sample", "create sample", "sample two sum", "sample code")
    ):
        return True

    return False


def _line_looks_like_code(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith(("//", "/*", "*", "#", "@")):
        return True
    if any(stripped.startswith(marker) for marker in _CODE_LINE_MARKERS):
        return True
    if re.search(r"[{}();:=\[\]<>]", stripped):
        return True
    return False


def _infer_language(code: str, fence_hint: str | None = None) -> str:
    if fence_hint:
        hint = fence_hint.lower()
        if hint in ("ts", "typescript"):
            return "typescript"
        if hint in ("py", "python"):
            return "python"
        if hint in ("java",):
            return "java"
        if hint in ("js", "javascript"):
            return "javascript"

    lower = code.lower()
    if "interface " in lower or "export interface" in lower or ": number" in lower:
        return "typescript"
    if lower.startswith("def ") or "import " in lower and "from " in lower:
        return "python"
    if "public class" in lower or "public static" in lower:
        return "java"
    return "javascript"


def looks_like_pasted_code(prompt: str) -> bool:
    """Heuristic: prompt is mostly a code snippet the user wants explained."""
    return extract_pasted_code(prompt) is not None


def extract_pasted_code(prompt: str) -> PastedCode | None:
    """Return extracted code lines and a language hint, or None."""
    text = (prompt or "").strip()
    if not text:
        return None

    fence = re.search(
        r"```(?:([\w+-]+)\s*)?\n(.*?)```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fence:
        body = fence.group(2).rstrip("\n")
        if body.strip():
            lines = body.splitlines()
            if len(lines) >= 2:
                return PastedCode(
                    lines=lines,
                    language=_infer_language(body, fence.group(1)),
                )

    lines = text.splitlines()
    if len(lines) < 3:
        return None

    code_like = sum(1 for line in lines if _line_looks_like_code(line))
    if code_like < max(3, int(len(lines) * 0.55)):
        return None

    joined = "\n".join(lines)
    return PastedCode(lines=lines, language=_infer_language(joined))
