"""Shared JSON contract text for math/science trunk subtypes."""

from __future__ import annotations

from .shared import (
    CANVAS_BACKGROUND,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    TRUNK_FORBIDDEN_ITEM_KEYS,
    TRUNK_FORBIDDEN_TOP_LEVEL,
)


def trunk_system_prompt(
    *,
    title: str,
    layout_mode: str,
    example_json: str,
    pedagogy: str,
    domain_rules: str = "",
) -> str:
    """Build a focused system prompt for one trunk subtype."""
    extra = f"\n{domain_rules}\n" if domain_rules else ""
    return f"""{title}

You ALWAYS emit a single ``DrawingStage`` JSON object with ``layoutMode: "{layout_mode}"`` (horizontal step row). The frontend owns all positions, sizes, colors, and animation. You only supply **content and teaching order**.

## REQUIRED JSON SHAPE

```json
{example_json}
```

## STRICT RULES

- Canvas: ``width: {CANVAS_WIDTH}``, ``height: {CANVAS_HEIGHT}``, ``background: "{CANVAS_BACKGROUND}"``, ``layoutMode: "{layout_mode}"``.
- **Never** emit ``CodeDisplay``.
- **Never** emit ``console`` TextCreation.
- Exactly one ``code-title`` (problem/topic) and one ``objective`` (learning goal).
- Steps are ``BoxCreation`` with unique ``id`` and ``text`` (string or string[]). Short lines (~18 chars).
- ``connections``: ``LineCreation`` links consecutive ``BoxCreation`` ids only.
- **Forbidden item keys:** {TRUNK_FORBIDDEN_ITEM_KEYS}.
- **Forbidden top-level keys:** {TRUNK_FORBIDDEN_TOP_LEVEL}.
- **Final answer** must be in the **last** ``BoxCreation``, not only in ``objective``.
{extra}
## PEDAGOGY FOR THIS SUBTYPE

{pedagogy}

## OUTPUT

Return ONLY one raw JSON object. No markdown fences. No commentary. Stop after the closing brace."""


def math_produce_line() -> str:
    return (
        f'layoutMode="math", width={CANVAS_WIDTH}, height={CANVAS_HEIGHT}, '
        f'background="{CANVAS_BACKGROUND}". No CodeDisplay. No console.'
    )


def science_produce_line() -> str:
    return (
        f'layoutMode="science", width={CANVAS_WIDTH}, height={CANVAS_HEIGHT}, '
        f'background="{CANVAS_BACKGROUND}". No CodeDisplay. No console.'
    )
