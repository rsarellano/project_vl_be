"""Shared code-map JSON contract for coding subtypes."""

from __future__ import annotations

from app.services.ai_services.drawing_stage.shared import (
    CANVAS_BACKGROUND,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
)

CODE_DERIVATION_PEDAGOGY = """\
## LAYER 2 — ``derivation`` ON EVERY LINKED EXPLAIN BOX

Each ``BoxCreation`` with ``linkedPortion`` MUST include a ``derivation`` object. \
This powers the expanded **"How this works"** panel when the learner clicks the short card \
(same role as math's "How we got here").

- Keep ``text`` SHORT (2–3 lines) for the sticky note beside the code.
- Put the real teaching depth ONLY in ``derivation.beats`` — never duplicate the short card \
as the only expand content.
- ``fromStepId``: the ``CodeDisplay`` id (usually ``"source"``) or the previous portion's \
explain box id when order matters.
- ``beats``: ordered playback script (one object = one fade-in line). Allowed types for coding:
  - ``{"type": "note", "text": "..."}`` — context / goal of this portion
  - ``{"type": "expression", "text": "...", "tokens": [{"lexeme":"===","explain":"..."}]}`` \
— a short **code** snippet (verbatim from ``CodeDisplay``). ``tokens`` is optional but \
strongly preferred: one entry per keyword, name, operator, or punctuation the learner \
should hover. Himay-himayin the line (break it into pieces), not a paraphrase of the whole line.
  - ``{"type": "arrow", "direction": "down"}``
  - ``{"type": "explain", "text": "..."}`` — teaching prose; use **3–6** explains typically

### Standard beat order

1. note — what this portion is and why it exists
2. expression — the key line(s), with ``tokens`` that dissect every keyword / name / operator
3. arrow
4. explain beats — how the pieces work together, edge cases, common mistakes
5. optional closing note — what happens next / how it connects to the next portion

### Portion-specific depth

- **Setup / declarations:** why the structure or variables are needed before the main logic.
- **Loops / CHECK / conditions:** walk concrete iterations when helpful \
(``i = 0 → true``, ``i = 1 → true``, … until false). Name the condition and the outcome.
- **Body / scan / update:** what changes each pass; what stays the same.
- **Return / result:** what is returned and why that value answers the problem.

Phrase explains as teaching sentences, not telegraphic labels. \
Start a beat with ``Why:`` when naming the design reason behind a structural choice."""


def code_map_system_prompt(*, title: str, example_json: str, pedagogy: str) -> str:
    return f"""{title}

You emit a single ``DrawingStage`` with ``layoutMode: "code-map"``. Frontend renders code panel + highlighted portions + explanation boxes. You never emit coordinates or styling.

## REQUIRED JSON SHAPE

```json
{example_json}
```

## STRICT RULES

- ``width: {CANVAS_WIDTH}``, ``height: {CANVAS_HEIGHT}``, ``background: "{CANVAS_BACKGROUND}"``, ``layoutMode: "code-map"``.
- Exactly one ``CodeDisplay`` (``text`` = one string per code line; ``portions`` with ``lines: [start, end]`` 0-based inclusive).
- One ``BoxCreation`` per portion with ``linkedPortion`` = portion ``id``.
- ``connections``: ``[]``. No ``TextCreation`` items except the optional ``AnswerBox`` card.
- Optional: one ``BoxCreation`` with ``AnswerBox: true`` and no ``linkedPortion`` for the worked answer (example result + complexity) under the code panel.
- Forbidden item keys: ``type``, ``x``, ``y``, ``width``, ``height``, ``role``, ``animation``, etc.
- Forbidden top-level: ``lines``, ``layoutHint``, ``explanation``, ``narrationBeats``.

## PEDAGOGY FOR THIS SUBTYPE

{pedagogy}

{CODE_DERIVATION_PEDAGOGY}

## OUTPUT

Return ONLY one raw JSON object. No markdown. Stop after the closing brace."""


def code_map_produce_line(*, pasted: bool) -> str:
    if pasted:
        return (
            'code-map layout. CodeDisplay.text = user snippet verbatim. '
            "Each linked BoxCreation needs short text PLUS derivation.beats. "
            f'layoutMode="code-map", width={CANVAS_WIDTH}, height={CANVAS_HEIGHT}.'
        )
        return (
            "code-map layout. Full solution in CodeDisplay.text (never the problem statement). "
            "CodeDisplay.text is one complete program of at most 100 lines: the core solution only, "
            "with no extra files, demo harness, or unused helpers. "
            "Each linked BoxCreation needs short text PLUS derivation.beats. "
            "Also emit one AnswerBox: true card with the example result and complexity. "
            f'layoutMode="code-map", width={CANVAS_WIDTH}, height={CANVAS_HEIGHT}.'
        )
