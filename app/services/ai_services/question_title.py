"""Short display titles for saved tutor answers (not the raw merge / OCR dump)."""

from __future__ import annotations

import re

_TITLE_FIELD = re.compile(r"(?:\*\*)?title(?:\*\*)?\s*:\s*(.+)", re.IGNORECASE)
_SKIP_LINE = re.compile(
    r"^(important:|problem from image:|input\s*:|output\s*:|example\s*\d|"
    r"constraints?:|\*\*example|\*\*constraints|\*\*statement)",
    re.IGNORECASE,
)
_MACHINE_PREFIX = re.compile(
    r"^(explain and walk through this programming problem|"
    r"explain and walk through|then give a working solution)",
    re.IGNORECASE,
)


_SUPERSCRIPTS = {
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
    "+": "⁺",
    "-": "⁻",
    "−": "⁻",
    "n": "ⁿ",
}
_PRETTY_MATH = re.compile(
    r"\\(?:d?frac|tfrac|cdot|times|div|sqrt|left|right|lim|to|infty|[()\[\]])|\^|√|->|→"
)
_LEADING_VERB = re.compile(
    r"^(simplify|solve|find|evaluate|calculate|expand|factor|differentiate)\b",
    re.IGNORECASE,
)
_PLAIN_TOKEN = re.compile(r"^[0-9A-Za-z⁰¹²³⁴⁵⁶⁷⁸⁹√.]+$")


def _clean_title(value: str) -> str:
    compact = re.sub(r"\*+", "", value or "")
    compact = re.sub(r"[`\"']+", "", compact)
    compact = re.sub(r"\s+", " ", compact).strip().rstrip(".:")
    if not compact:
        return "Untitled question"
    if len(compact) <= 72:
        return compact
    return f"{compact[:69].rstrip()}…"


def _read_brace_group(source: str, open_index: int) -> tuple[str, int] | None:
    if open_index >= len(source) or source[open_index] != "{":
        return None
    depth = 0
    for index in range(open_index, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[open_index + 1 : index], index + 1
    return None


def _to_superscript(body: str) -> str:
    return "".join(_SUPERSCRIPTS.get(char, char) for char in body)


def _last_char(value: str) -> str:
    trimmed = value.rstrip()
    return trimmed[-1] if trimmed else ""


def _wrap_frac_part(part: str) -> str:
    trimmed = part.strip()
    if not trimmed or _PLAIN_TOKEN.match(trimmed):
        return trimmed
    return f"({trimmed})"


def _latex_to_plain(source: str) -> str:
    index = 0
    out = ""
    while index < len(source):
        if source.startswith(("\\(", "\\)"), index):
            out += source[index + 1]
            index += 2
            continue
        if source.startswith(("\\[", "\\]"), index):
            index += 2
            continue
        if source.startswith(("\\{", "\\}"), index):
            out += "(" if source[index + 1] == "{" else ")"
            index += 2
            continue

        if source.startswith("\\lim", index):
            cursor = index + (7 if source.startswith("\\limits", index) else 4)
            while cursor < len(source) and source[cursor] == " ":
                cursor += 1
            if cursor < len(source) and source[cursor] == "_":
                group = _read_brace_group(source, cursor + 1)
                if group is not None:
                    out += f"lim {_latex_to_plain(group[0])} "
                    index = group[1]
                    continue
            out += "lim "
            index = cursor
            continue

        if source.startswith("\\to", index) and not (
            index + 3 < len(source) and source[index + 3].isalpha()
        ):
            out = f"{out.rstrip()}→"
            index += 3
            continue

        if source.startswith("->", index) or source[index] == "→":
            out = f"{out.rstrip()}→"
            index += 1 if source[index] == "→" else 2
            continue

        if source.startswith("\\infty", index):
            out += "∞"
            index += 6
            continue

        if source.startswith(("\\frac", "\\dfrac", "\\tfrac"), index):
            command_length = 5 if source.startswith("\\frac", index) else 6
            cursor = index + command_length
            while cursor < len(source) and source[cursor] == " ":
                cursor += 1
            numerator = _read_brace_group(source, cursor)
            if numerator is None:
                out += source[index]
                index += 1
                continue
            cursor = numerator[1]
            while cursor < len(source) and source[cursor] == " ":
                cursor += 1
            denominator = _read_brace_group(source, cursor)
            if denominator is None:
                out += source[index]
                index += 1
                continue
            top = _wrap_frac_part(_latex_to_plain(numerator[0]))
            bottom = _wrap_frac_part(_latex_to_plain(denominator[0]))
            if re.fullmatch(r"d[a-zA-Z]?", top) and re.fullmatch(r"d[a-zA-Z]", bottom):
                out += f"{top}/{bottom} "  # derivative operator: d/dx
            else:
                out += f"{top} / {bottom}"
            index = denominator[1]
            continue

        if source.startswith("\\sqrt", index):
            cursor = index + 5
            while cursor < len(source) and source[cursor] == " ":
                cursor += 1
            group = _read_brace_group(source, cursor)
            if group is not None:
                out += f"√({_latex_to_plain(group[0])})"
                index = group[1]
                continue

        if source.startswith(("\\cdot", "\\times"), index):
            out += " × "
            index += 5 if source.startswith("\\cdot", index) else 6
            continue

        if source.startswith("\\div", index):
            out += " ÷ "
            index += 4
            continue

        if source.startswith(("\\left", "\\right"), index):
            index += 5 if source.startswith("\\left", index) else 6
            continue

        if source[index] == "^":
            index += 1
            if index < len(source) and source[index] == "{":
                group = _read_brace_group(source, index)
                if group is not None:
                    out += _to_superscript(re.sub(r"\s", "", _latex_to_plain(group[0])))
                    index = group[1]
                    continue
            if index < len(source):
                out += _to_superscript(source[index])
                index += 1
                continue

        if source[index] in "-−":
            previous = _last_char(out)
            if previous and previous not in "(/×÷=−":
                out = f"{out.rstrip()} − "
            else:
                out += "−"
            index += 1
            continue

        if source[index] == "+":
            previous = _last_char(out)
            if previous and previous != "(":
                out = f"{out.rstrip()} + "
                index += 1
                continue

        if source[index] == "*" and not source.startswith("**", index):
            out += " × "
            index += 1
            continue

        if source[index].isspace():
            if out and not out.endswith(" "):
                out += " "
            index += 1
            continue

        out += source[index]
        index += 1

    out = re.sub(r"\s+", " ", out).strip()
    return out.replace("→ ", "→").replace("( ", "(").replace(" )", ")")


def _instruction_word(instruction: str, expression: str = "") -> str | None:
    text = instruction or ""
    if re.search(r"\bderivative\b|\bdifferentiate\b", text, re.IGNORECASE) or re.search(
        r"\bd/d[a-zA-Z]\b", expression
    ):
        return "Derivative"
    if re.search(r"\blimit\b", text, re.IGNORECASE) or re.search(r"\blim\b", expression):
        return "Limit"
    verb = _LEADING_VERB.match(text)
    return verb.group(1).capitalize() if verb else None


def _split_instruction(line: str) -> tuple[str | None, str]:
    trimmed = line.strip()
    colon = trimmed.find(":")
    if colon > 0:
        label = trimmed[: colon + 1]
        rest = trimmed[colon + 1 :].strip()
        words = label.replace(":", "").strip()
        if rest and _LEADING_VERB.match(words) and (
            _PRETTY_MATH.search(rest) or re.search(r"\d", rest)
        ):
            return label.strip(), rest
    return None, trimmed


def _simple_math_title(line: str) -> str | None:
    if not _PRETTY_MATH.search(line):
        return None
    instruction, math = _split_instruction(line)
    expression = _latex_to_plain(math or line)
    if not expression:
        return None
    word = _instruction_word(instruction or "", expression)
    if word:
        return _clean_title(f"{word}: {expression}")
    return _clean_title(expression)


def _display_line(line: str) -> str:
    return _simple_math_title(line) or _clean_title(line)


def title_from_stage(stage: object) -> str | None:
    """Use the stage problem line (the same text shown above the diagram)."""
    if not isinstance(stage, dict):
        return None
    objects = stage.get("objects")
    if not isinstance(objects, list):
        return None
    for obj in objects:
        if not isinstance(obj, dict) or obj.get("role") != "code-title":
            continue
        text = obj.get("text")
        if isinstance(text, str):
            lines = [text]
        elif isinstance(text, list):
            lines = [str(line) for line in text]
        else:
            continue
        title = " ".join(line.strip() for line in lines if str(line).strip())
        if title:
            return _display_line(title)
    return None


def title_from_prompt(prompt: str | None) -> str:
    text = (prompt or "").strip()
    if not text:
        return "Untitled question"

    titled = _TITLE_FIELD.search(text)
    if titled and titled.group(1).strip():
        return _clean_title(titled.group(1))

    skip_important = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            skip_important = False
            continue
        lower = line.lower()
        if lower.startswith("important:"):
            skip_important = True
            continue
        if skip_important and (line.startswith("- ") or line.startswith("• ")):
            continue
        skip_important = False
        if _MACHINE_PREFIX.match(line) or _SKIP_LINE.match(line):
            continue
        if lower.startswith("codedisplay") or lower.startswith("answerbox"):
            continue
        pretty = _display_line(line)
        if "\\" in pretty or "{" in pretty:
            whole = _simple_math_title(re.sub(r"\s+", " ", text))
            if whole and "\\" not in whole and "{" not in whole:
                return whole
        return pretty

    return _display_line(text)
