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
- ``BoxCreation.text`` and ``TextCreation.text`` MUST be **plain strings only** (or arrays of strings). \
**Never** nest beat objects like ``{{"type": "expression", "text": "2x = 10"}}`` inside ``text`` — \
those belong only in ``derivation.beats``.
- Chained equalities (``2x = y + 1 = 10``) are valid: put the full statement in ``code-title``, then split \
into separate plain-text equations in step boxes when solving (``2x = 10``, ``y + 1 = 10``).
- ``connections``: ``LineCreation`` links consecutive ``BoxCreation`` ids only.
- **Forbidden item keys:** {TRUNK_FORBIDDEN_ITEM_KEYS}.
- **Forbidden top-level keys:** {TRUNK_FORBIDDEN_TOP_LEVEL}.
- **Final answer** must be in the **last** ``BoxCreation``, not only in ``objective``.
{extra}
## PEDAGOGY FOR THIS SUBTYPE

{pedagogy}

## OUTPUT

Return ONLY one raw JSON object. No markdown fences. No commentary. Stop after the closing brace."""


MATH_DERIVATION_PEDAGOGY = """\
## LAYER 2 — ``derivation`` ON EVERY STEP BOX

Each ``BoxCreation`` that changes the math (every step after the first, and the first step \
when it rewrites the original problem) MUST include a ``derivation`` object explaining **why** \
that step was taken and **how each side changed**. This powers the right-hand "How we got here" panel.

- ``fromStepId``: ``id`` of the previous ``BoxCreation``. For the first transform from the \
given problem, use the ``code-title`` object id (usually ``"problem"``).
- ``beats``: ordered playback script — one object = one fade-in line. Allowed types only:
  - ``{"type": "note", "text": "..."}``
  - ``{"type": "expression", "text": "..."}`` — plain math (``sqrt(2x+5)``, ``x^2``; not LaTeX)
  - ``{"type": "arrow", "direction": "down"}``
  - ``{"type": "explain", "text": "..."}`` — **as many as the step needs** (often 3–5 for \
equation steps). Use plain math in prose (``sqrt(2x+5)``, ``(x+1)^2``) — **never LaTeX** \
(no ``\\sqrt{}``); the frontend renders math.
- Standard order: start note → previous expression → arrow → what we're doing (note) → \
explain beats (see below) → arrow → result note → new expression.
- First step from the original: start note = ``We start from the original equation.``
- Later steps: start note = ``We start from the previous step.``

### Two-sided equations — do NOT skip a side

When **both sides** of an equation change, include **separate explain beats for the left side \
AND the right side**. Never stop after explaining only one side.

Examples (adapt numbers/terms to the problem):
- **Square both sides:** one explain for the left (``sqrt(2x+5)`` squared → ``2x + 5``) and one \
for the right (``x + 1`` squared → ``(x+1)^2``).
- **Expand / simplify:** one explain per side with the **actual result** — e.g. right side \
``(x+1)^2`` expands to ``x^2 + 2x + 1`` (show FOIL or ``(a+b)^2``); left side ``2x + 5`` if \
already simplified.
- **Move a term:** explain what leaves one side and what appears on the other.

### Expansions must be WALKED, not jumped (FOIL / distributing)

A squaring or distribution step (``(x+1)^2``, ``2(x-3)``, ``(2x+5)^2``) must NOT jump straight \
to the final polynomial. Break the work into intermediate explain beats AND give the \
``motion_stage`` explicit ``frames`` so the box morphs through each stage. For ``(x+1)^2``:

- explains (one short beat each): ``(x+1)^2 means (x+1)(x+1)`` → ``First: x times x = x^2`` → \
``Outer and Inner: x times 1 and 1 times x = x + x`` → ``Last: 1 times 1 = 1`` → \
``Combine like terms: x + x = 2x``.
- ``motion_stage`` frames showing the same progression as the full equation, e.g.: \
``["2x + 5 = (x+1)^2", "2x + 5 = (x+1)(x+1)", "2x + 5 = x^2 + x + x + 1", "2x + 5 = x^2 + 2x + 1"]``.

Keep each explain to one line. The goal is the learner sees WHERE ``2x`` comes from, not just \
the final ``x^2 + 2x + 1``.

Phrase side-specific explains clearly: ``The left side: ...`` / ``The right side: ...``

### Explain the WHY behind structural moves (not just the mechanics)

When a step rearranges the equation to **unlock the next technique**, add ONE short \
``explain`` beat (1–2 sentences) that gives the reason — what goal it serves and why it is \
allowed — before the mechanics. **Start this beat with the word ``Why``** (e.g. \
``Why: ...``) so the panel shows it as a highlighted reason callout. Keep it summarized, not \
a paragraph.

- **Move all terms to one side (set = 0):** a quadratic (it has an ``x^2`` term) must equal \
zero before you can factor or use the quadratic formula, so subtract the same terms from both \
sides to clear one side to ``0`` while keeping the equation balanced.
- **Isolate a variable / radical:** the term must stand alone before the inverse operation \
(square, divide, etc.) can be applied cleanly.
- **Clear fractions or common factors:** removes denominators so the equation is easier to solve.

Pattern for one tight beat: name the **goal**, the **inverse operation** used, and the \
**balance rule** (same thing to both sides) — in a single sentence or two. Example: \
``Why: a quadratic must equal 0 before we can factor it, so we subtract 2x and 5 from both \
sides (same operation each side keeps it balanced).``

### Cinematic ``motion`` beats (stickers + animation)

Use **sparingly** — only when a term visibly moves, cancels, or should be highlighted. \
Most beats stay KaTeX; ``motion`` renders that one frame with **sticker SVGs** so the frontend can animate glyphs.

```json
{
  "type": "motion",
  "text": "sqrt(2x+5) - x = 1",
  "id": "mv1",
  "term": "-x",
  "motion": "slide_right"
}
```

- ``text``: full expression for that frame (plain math).
- ``term``: consecutive characters to animate (e.g. ``"-x"``, ``"x"``).
- ``motion``: one of ``slide_right``, ``slide_left``, ``highlight``, ``fade_in``.
- Place after the explain that introduces the move; follow with arrow + result expression (KaTeX is fine).

### ``motion_stage`` — animated equation box after the explains

After the explain beats, add a ``motion_stage`` beat: an animated box that **morphs the \
equation** from its previous form into its new form (KaTeX crossfade).

```json
{
  "type": "motion_stage",
  "id": "stage-square",
  "operation": "squared"
}
```

- The frontend **auto-derives** the before/after equations from the surrounding \
``expression`` beats, so usually you only need ``{"type": "motion_stage"}``.
- Optional ``from`` / ``to`` (plain math) override the auto-derived equations.
- Optional ``frames``: explicit list of plain-math equations to morph through in order. \
**Required for expand/FOIL/distribute steps** — include each intermediate form so the \
expansion is animated stage by stage (see "Expansions must be WALKED" above).
- **``operation`` is REQUIRED for every "do the same to both sides" step** (add/subtract \
a term, multiply/divide both sides). Give the exact signed term applied to both sides in \
plain math: ``"+x"``, ``"-5"``, ``"\\times 2"``, ``"/3"``. It is shown floating above each \
side while the ``=`` stays fixed (e.g. ``"+x"`` hovering over both sides to show the ``-x`` \
being cancelled). Also set ``from`` and ``to`` explicitly on these steps (full equations in \
plain math, each containing ``=``) so the box never has to guess. Omit ``operation`` only for \
non-balancing transforms (squaring already isolated radicals, simplifying one side, FOIL).
- Place **immediately after** the last explain, **before** the final arrow + result expression.

- Do NOT emit layout, colors, animation timings, or coordinates — content only."""


def math_trunk_system_prompt(
    *,
    title: str,
    example_json: str,
    pedagogy: str,
    domain_rules: str = "",
) -> str:
    """Math trunk prompt with shared layer-2 derivation rules."""
    return trunk_system_prompt(
        title=title,
        layout_mode="math",
        example_json=example_json,
        pedagogy=f"{pedagogy}\n\n{MATH_DERIVATION_PEDAGOGY}",
        domain_rules=domain_rules,
    )


def math_produce_line() -> str:
    return (
        f'layoutMode="math", width={CANVAS_WIDTH}, height={CANVAS_HEIGHT}, '
        f'background="{CANVAS_BACKGROUND}". No CodeDisplay. No console. '
        "Every equation-transform step box MUST include derivation.beats."
    )


def science_produce_line() -> str:
    return (
        f'layoutMode="science", width={CANVAS_WIDTH}, height={CANVAS_HEIGHT}, '
        f'background="{CANVAS_BACKGROUND}". No CodeDisplay. No console.'
    )
