"""Math · algebra — equations, variables, symbolic manipulation."""

from app.services.ai_services.drawing_stage._prompt_types import SubtypePrompt
from app.services.ai_services.drawing_stage._trunk_contract import math_produce_line, trunk_system_prompt

EXAMPLE = """{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "layoutMode": "math",
  "objects": [
    { "id": "problem", "TextCreation": true, "role": "code-title", "text": ["4x + 5 + 2x - 1"] },
    { "id": "objective", "TextCreation": true, "role": "objective", "text": ["Objective:", "Simplify the expression"] },
    { "id": "step-1", "BoxCreation": true, "text": ["Group like terms", "", "x terms: 4x, 2x", "constants: 5, -1"] },
    { "id": "step-2", "BoxCreation": true, "text": ["Combine x terms", "", "4x + 2x = 6x"] },
    { "id": "step-3", "BoxCreation": true, "text": ["Combine constants", "", "5 - 1 = 4"] },
    { "id": "step-4", "BoxCreation": true, "text": ["Put groups together", "", "6x + 4"] },
    { "id": "result", "BoxCreation": true, "text": ["Simplified Expression", "", "6x + 4"] }
  ],
  "connections": [
    { "LineCreation": true, "from": "step-1", "to": "step-2" },
    { "LineCreation": true, "from": "step-2", "to": "step-3" },
    { "LineCreation": true, "from": "step-3", "to": "step-4" },
    { "LineCreation": true, "from": "step-4", "to": "result" }
  ]
}"""

PEDAGOGY = """\
- ``code-title`` = the equation, expression, or system given (one clear statement).
- **Simplify expressions (required shape):** box 1 = ``Group like terms`` (all variable terms + constants). \
Then **one box per combine step**: combine variable terms with arithmetic shown (``4x + 2x = 6x``), \
combine constants with arithmetic shown (``5 - 1 = 4``), then ``Put groups together`` (``6x + 4``). \
Last box = ``Simplified Expression``.
- Never skip the constants combine box when constants exist. Show ``+``/``-`` work explicitly.
- **Solve equations:** given → inverse operations in order (isolate variable) → optional check → **last box = solution**.
- Show **each transformed equation** on its own line inside a box (e.g. ``2x = 8`` after subtracting 6).
- For quadratics/factoring, add boxes per logical move (factor, zero-product, roots).
- Use symbols consistently; do not skip algebraic steps the learner must see."""

SYSTEM = trunk_system_prompt(
    title="You design **algebra** diagrams (equations and symbolic solving).",
    layout_mode="math",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="math",
    subtype="algebra",
    layout_mode="math",
    system=SYSTEM,
    human_hint=(
        "Apply only algebra moves relevant to the prompt. "
        "Simplify expressions → last box = simplified form; equations → last box = solved value(s)."
    ),
    produce_line=f"Produce one algebra DrawingStage. {math_produce_line()}",
)
