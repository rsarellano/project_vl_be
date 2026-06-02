"""Shared code-map JSON contract for coding subtypes."""

from __future__ import annotations

from app.services.ai_services.drawing_stage.shared import (
    CANVAS_BACKGROUND,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
)


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
- ``connections``: ``[]``. No ``TextCreation`` items.
- Forbidden item keys: ``type``, ``x``, ``y``, ``width``, ``height``, ``role``, ``animation``, etc.
- Forbidden top-level: ``lines``, ``layoutHint``, ``explanation``, ``narrationBeats``.

## PEDAGOGY FOR THIS SUBTYPE

{pedagogy}

## OUTPUT

Return ONLY one raw JSON object. No markdown. Stop after the closing brace."""


def code_map_produce_line(*, pasted: bool) -> str:
    if pasted:
        return (
            'code-map layout. CodeDisplay.text = user snippet verbatim. '
            f'layoutMode="code-map", width={CANVAS_WIDTH}, height={CANVAS_HEIGHT}.'
        )
    return (
        "code-map layout. Full solution in CodeDisplay.text. "
        f'layoutMode="code-map", width={CANVAS_WIDTH}, height={CANVAS_HEIGHT}.'
    )
