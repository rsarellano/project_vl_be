"""Math · algebra — equations, variables, symbolic manipulation."""

from app.services.ai_services.drawing_stage._prompt_types import SubtypePrompt
from app.services.ai_services.drawing_stage._trunk_contract import math_produce_line, trunk_system_prompt

EXAMPLE = """{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "layoutMode": "math",
  "objects": [
    { "id": "problem", "TextCreation": true, "role": "code-title", "text": ["2x + 6 = 14"] },
    { "id": "objective", "TextCreation": true, "role": "objective", "text": ["Objective:", "Solve for x"] },
    { "id": "step-1", "BoxCreation": true, "text": ["Given", "", "2x + 6 = 14"] },
    { "id": "step-2", "BoxCreation": true, "text": ["Subtract 6", "", "2x = 8"] },
    { "id": "step-3", "BoxCreation": true, "text": ["Divide by 2", "", "x = 4"] },
    { "id": "check", "BoxCreation": true, "text": ["Check", "", "2(4)+6=14", "True"] },
    { "id": "result", "BoxCreation": true, "text": ["Solution", "", "x = 4"] }
  ],
  "connections": [
    { "LineCreation": true, "from": "step-1", "to": "step-2" },
    { "LineCreation": true, "from": "step-2", "to": "step-3" },
    { "LineCreation": true, "from": "step-3", "to": "check" },
    { "LineCreation": true, "from": "check", "to": "result" }
  ]
}"""

PEDAGOGY = """\
- ``code-title`` = the equation or system given (one clear statement).
- Boxes: write given → inverse operations in order (isolate variable) → optional check → **last box = solution**.
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
    human_hint="Apply only algebra moves relevant to the user's equation. Last box = solved value(s).",
    produce_line=f"Produce one algebra DrawingStage. {math_produce_line()}",
)
