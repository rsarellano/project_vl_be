"""Line-by-line explanation for pasted source.

The full DrawingStage tool schema is large enough that a walkthrough often
fails validation. This path asks only for one note per line, then builds a
valid code-map stage locally.
"""

from __future__ import annotations

import asyncio
import logging
import os

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.schemas.infographics_schema import DrawingStage
from app.services.ai_services.llm_client import build_chat_model

logger = logging.getLogger(__name__)

_SYSTEM = """\
You explain source code one line at a time for a visual tutor.

The snippet is already written. Do not rewrite it, and do not skip a numbered line.
Python 3 is valid here, including classes, default arguments, None, and divmod.

For every non-blank numbered line return:
- line: the 1-based number printed beside that line
- title: 2 to 5 words naming what that line does
- explain: one or two teaching sentences about that line only
"""


class CodeLineNote(BaseModel):
    line: int = Field(description="1-based line number from the numbered snippet.")
    title: str = Field(description="2 to 5 word card title.")
    explain: str = Field(description="One or two sentences about this line only.")


class CodeWalkthrough(BaseModel):
    notes: list[CodeLineNote] = Field(default_factory=list)


class CodeSectionNote(BaseModel):
    section: int = Field(description="1-based section number from the prompt.")
    title: str = Field(description="2 to 5 word card title for the whole section.")
    explain: str = Field(description="Two or three sentences about this section, not each line.")


class CodeSectionWalkthrough(BaseModel):
    notes: list[CodeSectionNote] = Field(default_factory=list)


class CodePieceNote(BaseModel):
    line: int = Field(description="1-based line number from the numbered snippet.")
    lexeme: str = Field(description="One word or symbol copied exactly from that line.")
    explain: str = Field(description="One sentence about this piece in this line.")


class CodePieceWalkthrough(BaseModel):
    pieces: list[CodePieceNote] = Field(default_factory=list)


_PIECE_SYSTEM = """\
You write hover notes for a visual code tutor.

Read the whole numbered snippet before you explain any piece. The meaning of a
symbol depends on the line it is in, not on a general definition.
- In querySelectorAll<SVGGeometryElement>, < opens a TypeScript type argument.
- In i < n, < means less than.
- querySelectorAll selects every element matching the CSS selector in the parentheses.

For every non-blank line, list the pieces a learner might hover, left to right:
keywords, names, calls, types, operators, and punctuation. Skip spaces.
lexeme is one word or one symbol from that line, copied exactly, never a whole statement.
explain is one sentence about this use in this line.
"""


_SECTION_STARTS = (
    "class ",
    "def ",
    "async def ",
    "while ",
    "for ",
    "return ",
)


def section_spans(lines: list[str]) -> list[tuple[int, int]]:
    """Group a snippet into class, function, loop, and return blocks."""
    if not lines:
        return []
    starts = [0]
    for index, line in enumerate(lines):
        if index == 0:
            continue
        if line.strip().startswith(_SECTION_STARTS):
            starts.append(index)
    spans: list[tuple[int, int]] = []
    for position, start in enumerate(starts):
        end = starts[position + 1] - 1 if position + 1 < len(starts) else len(lines) - 1
        spans.append((start, end))
    return spans


def _fallback_note(line: str) -> tuple[str, str]:
    stripped = line.strip()
    if stripped.startswith("#"):
        return "Comment", "This comment describes the code around it. It does not run."
    if stripped.startswith("class "):
        return "Define a class", "This line names a class. The indented lines below are its body."
    if stripped.startswith("def "):
        return "Define a function", "This line names a function and its parameters. The indented lines below run when it is called."
    if stripped.startswith("return "):
        return "Return a value", "This line hands a value back to the caller and ends the function."
    if stripped.startswith("while "):
        return "Repeat while true", "This loop keeps running the indented lines as long as its condition is true."
    if stripped.startswith("if ") or stripped.startswith("elif ") or stripped == "else:":
        return "Choose a branch", "This line decides whether the indented lines under it run."
    return "Run this line", f"This line runs as written: {stripped}"


def _notes_by_index(notes: list[CodeLineNote], line_count: int) -> dict[int, CodeLineNote]:
    if not notes or line_count <= 0:
        return {}
    zero_based = min(note.line for note in notes) == 0
    mapped: dict[int, CodeLineNote] = {}
    for note in notes:
        index = note.line if zero_based else note.line - 1
        if 0 <= index < line_count and note.explain.strip() and note.title.strip():
            mapped[index] = note
    return mapped


def _code_lines(lines: list[str]) -> list[str]:
    """Drop blank lines so portion indexes match the code panel."""
    return [line.rstrip("\n") for line in lines if line.strip()]


def _tokens_for_span(
    pieces: list[CodePieceNote],
    lines: list[str],
    start: int,
    end: int,
) -> list[dict]:
    """Keep hover notes whose lexeme really appears on that line."""
    if not pieces:
        return []
    zero_based = min(piece.line for piece in pieces) == 0
    tokens: list[dict] = []
    for piece in pieces:
        index = piece.line if zero_based else piece.line - 1
        if index < start or index > end:
            continue
        lexeme = piece.lexeme.strip()
        explain = " ".join(piece.explain.split())
        if not lexeme or not explain or lexeme not in lines[index]:
            continue
        tokens.append(
            {
                "lexeme": lexeme,
                "explain": explain,
                "line": index - start + 1,
            }
        )
    return tokens


def _append_portion(
    *,
    portions: list[dict],
    boxes: list[dict],
    previous_id: str,
    start: int,
    end: int,
    lines: list[str],
    title: str,
    explain: str,
    label: str,
    tokens: list[dict] | None = None,
) -> str:
    portion_id = f"lines-{start + 1}-{end + 1}"
    box_id = f"explain-{portion_id}"
    excerpt = "\n".join(line.strip() for line in lines[start : end + 1] if line.strip())
    portions.append(
        {
            "id": portion_id,
            "lines": [start, end],
            "label": label,
        }
    )
    boxes.append(
        {
            "id": box_id,
            "BoxCreation": True,
            "linkedPortion": portion_id,
            "text": [title],
            "derivation": {
                "fromStepId": previous_id,
                "beats": [
                    {"type": "note", "text": title},
                    {
                        "type": "expression",
                        "text": excerpt[:500],
                        **({"tokens": tokens} if tokens else {}),
                    },
                    {"type": "arrow", "direction": "down"},
                    {"type": "explain", "text": explain},
                ],
            },
        }
    )
    return box_id


def assemble_line_explain_stage(
    lines: list[str],
    language: str,
    notes: list[CodeLineNote] | None = None,
    pieces: list[CodePieceNote] | None = None,
) -> dict:
    """Build a code-map stage with one explanation card per non-blank line."""
    lines = _code_lines(lines)
    by_index = _notes_by_index(notes or [], len(lines))
    portions: list[dict] = []
    boxes: list[dict] = []
    previous_id = "source"

    for index, line in enumerate(lines):
        if not line.strip():
            continue
        note = by_index.get(index)
        if note is None:
            title, explain = _fallback_note(line)
        else:
            title = " ".join(note.title.split())[:48]
            explain = " ".join(note.explain.split())
        previous_id = _append_portion(
            portions=portions,
            boxes=boxes,
            previous_id=previous_id,
            start=index,
            end=index,
            lines=lines,
            title=title,
            explain=explain,
            label=f"Line {index + 1}",
            tokens=_tokens_for_span(pieces or [], lines, index, index),
        )

    if not portions:
        raise ValueError("Pasted code has no lines to explain.")

    payload = {
        "width": 1400,
        "height": 1250,
        "background": "#ffffff",
        "layoutMode": "code-map",
        "objects": [
            {
                "id": "source",
                "CodeDisplay": True,
                "language": language or "python",
                "text": list(lines),
                "portions": portions,
            },
            *boxes,
        ],
        "connections": [],
    }
    return DrawingStage.model_validate(payload).model_dump(mode="json", by_alias=True)


def assemble_section_stage(
    lines: list[str],
    language: str,
    notes: list[CodeSectionNote] | None = None,
    pieces: list[CodePieceNote] | None = None,
) -> dict:
    """Build a code-map stage with one card per logical section."""
    lines = _code_lines(lines)
    spans = section_spans(lines)
    by_section = {
        note.section: note
        for note in notes or []
        if note.title.strip() and note.explain.strip()
    }
    portions: list[dict] = []
    boxes: list[dict] = []
    previous_id = "source"
    for position, (start, end) in enumerate(spans, start=1):
        note = by_section.get(position)
        if note is None:
            title, explain = _fallback_note(lines[start])
            if end > start:
                explain = (
                    f"{explain} The following lines in this block carry that idea through."
                )
        else:
            title = " ".join(note.title.split())[:48]
            explain = " ".join(note.explain.split())
        label = f"Lines {start + 1}–{end + 1}" if end > start else f"Line {start + 1}"
        previous_id = _append_portion(
            portions=portions,
            boxes=boxes,
            previous_id=previous_id,
            start=start,
            end=end,
            lines=lines,
            title=title,
            explain=explain,
            label=label,
            tokens=_tokens_for_span(pieces or [], lines, start, end),
        )
    if not portions:
        raise ValueError("Pasted code has no lines to explain.")
    payload = {
        "width": 1400,
        "height": 1250,
        "background": "#ffffff",
        "layoutMode": "code-map",
        "objects": [
            {
                "id": "source",
                "CodeDisplay": True,
                "language": language or "python",
                "text": list(lines),
                "portions": portions,
            },
            *boxes,
        ],
        "connections": [],
    }
    return DrawingStage.model_validate(payload).model_dump(mode="json", by_alias=True)


def _question_block(instruction: str) -> str:
    question = (instruction or "").strip()
    if not question:
        return ""
    return f"What the learner asked, read this before the code: {question}\n\n"


async def build_line_explain_stage(
    lines: list[str],
    language: str,
    *,
    api_key: str,
    instruction: str = "",
    line_by_line: bool = False,
) -> dict:
    """Explain pasted code. Line cards only when the learner asked for them."""
    lines = _code_lines(lines)
    numbered = "\n".join(f"{index + 1}| {line}" for index, line in enumerate(lines))
    question_block = _question_block(instruction)
    if not line_by_line:
        return await _build_section_stage(
            lines,
            language,
            question_block=question_block,
            api_key=api_key,
        )

    notes, pieces = await asyncio.gather(
        _line_notes(lines, language, question_block, api_key, numbered),
        _explain_pieces(lines, language, question_block, api_key),
    )

    return assemble_line_explain_stage(lines, language, notes, pieces)


async def _line_notes(
    lines: list[str],
    language: str,
    question_block: str,
    api_key: str,
    numbered: str,
) -> list[CodeLineNote]:
    llm = build_chat_model(temperature=0, model=_answer_model(), api_key=api_key)
    structured = llm.with_structured_output(CodeWalkthrough, method="function_calling")
    try:
        result = await structured.ainvoke(
            [
                SystemMessage(content=_SYSTEM),
                HumanMessage(
                    content=(
                        f"{question_block}"
                        f"Language: {language}\n"
                        "The learner asked for a line-by-line explanation. "
                        "Explain every non-blank line. Do not treat the question as code.\n\n"
                        f"{numbered}"
                    )
                ),
            ]
        )
    except Exception:
        logger.exception("Line-by-line notes failed; using short fallbacks.")
        return []
    if result is None:
        return []
    return list(result.notes)


async def _explain_pieces(
    lines: list[str],
    language: str,
    question_block: str,
    api_key: str,
) -> list[CodePieceNote]:
    """Hover sentences. The model sees the whole snippet, so each piece uses its line."""
    numbered = "\n".join(f"{index + 1}| {line}" for index, line in enumerate(lines))
    try:
        llm = build_chat_model(temperature=0, model=_answer_model(), api_key=api_key)
        structured = llm.with_structured_output(CodePieceWalkthrough, method="function_calling")
        result = await structured.ainvoke(
            [
                SystemMessage(content=_PIECE_SYSTEM),
                HumanMessage(
                    content=(
                        f"{question_block}"
                        f"Language: {language}\n"
                        "Read every numbered line before you write a note. "
                        "Explain each piece from the code around it.\n\n"
                        f"{numbered}"
                    )
                ),
            ]
        )
    except Exception:
        logger.exception("Piece notes failed; hover text will use the local backup.")
        return []
    if result is None:
        return []
    return list(result.pieces)


async def _build_section_stage(
    lines: list[str],
    language: str,
    *,
    question_block: str,
    api_key: str,
) -> dict:
    spans = section_spans(lines)
    listed = []
    for position, (start, end) in enumerate(spans, start=1):
        body = "\n".join(f"{index + 1}| {lines[index]}" for index in range(start, end + 1))
        listed.append(f"Section {position}:\n{body}")
    notes, pieces = await asyncio.gather(
        _section_notes(language, question_block, api_key, listed),
        _explain_pieces(lines, language, question_block, api_key),
    )
    return assemble_section_stage(lines, language, notes, pieces)


async def _section_notes(
    language: str,
    question_block: str,
    api_key: str,
    listed: list[str],
) -> list[CodeSectionNote]:
    llm = build_chat_model(temperature=0, model=_answer_model(), api_key=api_key)
    structured = llm.with_structured_output(CodeSectionWalkthrough, method="function_calling")
    try:
        result = await structured.ainvoke(
            [
                SystemMessage(
                    content=(
                        "You explain source code for a visual tutor. "
                        "Read the learner's question first, then explain the sections you are given. "
                        "Do not split a section into individual lines. "
                        "Python 3 is valid. Return one note per section number."
                    )
                ),
                HumanMessage(
                    content=(
                        f"{question_block}"
                        f"Language: {language}\n"
                        "Explain each section as a whole.\n\n"
                        + "\n\n".join(listed)
                    )
                ),
            ]
        )
    except Exception:
        logger.exception("Section notes failed; using short fallbacks.")
        return []
    if result is None:
        return []
    return list(result.notes)


def _answer_model() -> str:
    return os.getenv("OPENAI_ANSWER_MODEL", "gpt-4o")
