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
    "build a function",
    "how do i solve",
    "complete the function",
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
