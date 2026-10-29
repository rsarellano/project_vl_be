"""Detect and extract source code pasted into the user's prompt."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PastedCode:
    lines: list[str]
    language: str
    instruction: str = ""

MAX_PASTED_CODE_LINES = 80
MAX_WRITTEN_CODE_LINES = 100


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
    "elif ",
    "else:",
    "else ",
    "for ",
    "while ",
    "try:",
    "except",
    "finally:",
    "with ",
    "async ",
    "from ",
    "yield ",
    "raise ",
    "pass",
    "break",
    "continue",
    "extends ",
    "implements ",
)


_LINE_BY_LINE_KEYWORDS = (
    "line by line",
    "line-by-line",
    "line per line",
    "each line",
    "every line",
)


def user_asked_for_line_by_line(prompt: str) -> bool:
    """True only when the prose asks for a line-by-line walkthrough."""
    return any(keyword in _instruction_text(prompt) for keyword in _LINE_BY_LINE_KEYWORDS)


_EXPLAIN_KEYWORDS = (
    "explain this",
    "explain the",
    "explain line",
    "line by line",
    "line per line",
    "what does this",
    "walk me through",
    "walk through",
    "help me understand",
    "break down",
    "break this down",
)


def user_asked_to_explain(prompt: str) -> bool:
    """True when the prose around a snippet asks for an explanation."""
    return any(keyword in _instruction_text(prompt) for keyword in _EXPLAIN_KEYWORDS)


def user_asked_to_implement(prompt: str) -> bool:
    """True when the user wants a new solution, judged from the prose only."""
    if subtype_for_pasted_prompt(prompt) == "code_explain":
        return False
    return any(keyword in _instruction_text(prompt) for keyword in _IMPLEMENT_KEYWORDS)


def pasted_instruction(prompt: str) -> str:
    """The question written around a pasted snippet, without the source itself."""
    pasted = extract_pasted_code(prompt)
    if pasted is None:
        return (prompt or "").strip()
    return pasted.instruction


def _instruction_text(prompt: str) -> str:
    return pasted_instruction(prompt).lower()


def subtype_for_pasted_prompt(prompt: str) -> str | None:
    """Route from the split prompt. A pasted function body is always an explanation.

    Words such as "leetcode" or "solve" only request a new solution when they
    appear in the prose and the paste is a stub (or there is no paste).
    """
    pasted = extract_pasted_code(prompt)
    instruction = _instruction_text(prompt) if pasted is not None else (prompt or "").strip().lower()
    if pasted is not None:
        if user_asked_to_explain(prompt) or not _pasted_is_stub(pasted.lines):
            return "code_explain"
        if any(keyword in instruction for keyword in _IMPLEMENT_KEYWORDS):
            return "code_solution"
        return "code_explain"
    if looks_like_problem_statement(prompt):
        return "code_solution"
    return None


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


_ASSIGN_LINE = re.compile(
    r"^(?:[\w.]+(?:\s*,\s*[\w.]+)*)\s*(?:=|\+=|-=|\*=|/=|//=|:=)"
)
_CALL_LINE = re.compile(r"^[\w.]+\s*\(")
_STUB_LINES = frozenset({"pass", "...", "return", "raise notimplementederror"})


def _line_looks_like_code(line: str) -> bool:
    """True for a source line. Ordinary sentences are not code, even with a colon."""
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith(("//", "#", "/*", "*/", "@")):
        return True
    if stripped.startswith("*") and not re.search(r"[=(){};]", stripped):
        return False
    if any(stripped.startswith(marker) for marker in _CODE_LINE_MARKERS):
        return True
    if line[:1] in (" ", "\t") and re.search(r"[=(){}\[\]:]", stripped):
        return True
    if _ASSIGN_LINE.match(stripped) or _CALL_LINE.match(stripped):
        return True
    if stripped.endswith(("{", ";", "};", ")", "}")):
        return True
    return False


def _pasted_is_stub(lines: list[str]) -> bool:
    """True when the paste is only a signature, comments, or an empty body."""
    statements: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//", "/*", "*")):
            continue
        if stripped.startswith(
            ("def ", "async def ", "class ", "function ", "export ", "import ", "from ")
        ):
            continue
        statements.append(stripped.lower())
    if not statements:
        return True
    return all(
        statement in _STUB_LINES
        or statement.startswith("pass")
        or "your code" in statement
        or statement.startswith("todo")
        or statement.startswith("raise notimplementederror")
        for statement in statements
    )


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
    if re.search(r"(?m)^\s*(async\s+def|def)\b", code) or "self." in code:
        return "python"
    if re.search(r"(?m)^\s*class\s+\w+", code) and "function " not in lower:
        return "python"
    if "interface " in lower or "export interface" in lower or ": number" in lower:
        return "typescript"
    if "public class" in lower or "public static" in lower:
        return "java"
    return "javascript"


def looks_like_pasted_code(prompt: str) -> bool:
    """Heuristic: prompt is mostly a code snippet the user wants explained."""
    return extract_pasted_code(prompt) is not None


def _cap_code_lines(lines: list[str]) -> list[str]:
    """Keep code-map payloads snippet-sized for rendering and model stability."""
    if len(lines) <= MAX_PASTED_CODE_LINES:
        return lines
    return lines[:MAX_PASTED_CODE_LINES]


def looks_like_problem_statement(prompt: str) -> bool:
    """True when the prompt is a coding *problem* (LeetCode OCR), not source to explain."""
    text = (prompt or "").strip().lower()
    if not text:
        return False
    markers = (
        "explain and walk through this programming problem",
        "problem from image:",
        "example 1:",
        "example 1\n",
        "**example",
        "constraints:",
        "**constraints",
        "**title:**",
        "given two sorted arrays",
        "return the median",
    )
    if any(marker in text for marker in markers):
        return True
    has_io = "input:" in text and "output:" in text
    has_fn = any(
        token in text
        for token in ("function ", "def ", "const ", "class ", "=>")
    )
    return has_io and not has_fn


def _is_interleaved_prose(line: str) -> bool:
    """A question at column 0. Indented lines stay in the program (docstrings, body)."""
    if not line.strip():
        return False
    if line[:1] in (" ", "\t"):
        return False
    return not _line_looks_like_code(line)


def _split_code_and_prose(lines: list[str]) -> tuple[list[str], str]:
    """Pull learner sentences out of the top, middle, or bottom of a paste."""
    code: list[str] = []
    prose: list[str] = []
    for line in lines:
        if _is_interleaved_prose(line):
            prose.append(line.strip())
        else:
            code.append(line)
    while code and not code[0].strip():
        code.pop(0)
    while code and not code[-1].strip():
        code.pop()
    return code, re.sub(r"\s+", " ", " ".join(prose)).strip()


def _accept_code_lines(lines: list[str]) -> list[str] | None:
    if len(lines) < 2:
        return None
    code_like = sum(1 for line in lines if _line_looks_like_code(line))
    has_definition = any(
        line.strip().startswith(("def ", "async def ", "class ", "function "))
        for line in lines
    )
    if len(lines) < 3:
        if not has_definition or code_like < 2:
            return None
        return lines
    if code_like < max(3, int(len(lines) * 0.55)):
        return None
    return lines


def _partition_prompt(text: str) -> tuple[list[str] | None, str, str | None]:
    """Return code lines, the learner's words, and an optional fence language."""
    fence = re.search(
        r"```(?:([\w+-]+)\s*)?\n(.*?)```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fence:
        body = fence.group(2).rstrip("\n")
        code, inner = _split_code_and_prose(body.splitlines())
        outside = f"{text[:fence.start()]}\n{text[fence.end():]}"
        _, outer = _split_code_and_prose(outside.splitlines())
        prose = " ".join(part for part in (outer, inner) if part)
        return _accept_code_lines(code), re.sub(r"\s+", " ", prose).strip(), fence.group(1)
    code, prose = _split_code_and_prose(text.splitlines())
    return _accept_code_lines(code), prose, None


def _extract_raw_code_lines(prompt: str) -> list[str] | None:
    """Extract candidate code lines without applying snippet caps."""
    text = (prompt or "").strip()
    if not text:
        return None
    code, _prose, _hint = _partition_prompt(text)
    return code


def code_display_line_count(stage: dict) -> int:
    """How many lines the tutor put in the code panel."""
    for obj in stage.get("objects") or []:
        if not isinstance(obj, dict) or obj.get("CodeDisplay") is not True:
            continue
        text = obj.get("text")
        if isinstance(text, str):
            return len(text.splitlines())
        if isinstance(text, list):
            return len(text)
    return 0


def pasted_code_line_count(prompt: str) -> int | None:
    """Return detected pasted/typed code line count, or None when not code."""
    lines = _extract_raw_code_lines(prompt)
    if lines is None:
        return None
    return len(lines)


def extract_pasted_code(prompt: str) -> PastedCode | None:
    """Return extracted code lines and a language hint, or None."""
    text = (prompt or "").strip()
    if not text:
        return None
    raw_lines, instruction, fence_hint = _partition_prompt(text)
    if not raw_lines:
        return None
    lines = _cap_code_lines(raw_lines)
    return PastedCode(
        lines=lines,
        language=_infer_language("\n".join(lines), fence_hint),
        instruction=instruction,
    )
