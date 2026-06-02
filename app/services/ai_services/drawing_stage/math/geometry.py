"""Math · geometry — shapes, measures, formulas."""

from app.services.ai_services.drawing_stage._prompt_types import SubtypePrompt
from app.services.ai_services.drawing_stage._trunk_contract import math_produce_line, trunk_system_prompt

EXAMPLE = """{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "layoutMode": "math",
  "objects": [
    { "id": "problem", "TextCreation": true, "role": "code-title", "text": ["Right triangle", "base 6 cm", "height 4 cm"] },
    { "id": "objective", "TextCreation": true, "role": "objective", "text": ["Objective:", "Find the area"] },
    { "id": "step-1", "BoxCreation": true, "text": ["Known", "", "b = 6 cm", "h = 4 cm"] },
    { "id": "step-2", "BoxCreation": true, "text": ["Formula", "", "Area =", "(1/2) × b × h"] },
    { "id": "step-3", "BoxCreation": true, "text": ["Substitute", "", "(1/2)×6×4", "= 12"] },
    { "id": "result", "BoxCreation": true, "text": ["Answer", "", "Area = 12 cm²"] }
  ],
  "connections": [
    { "LineCreation": true, "from": "step-1", "to": "step-2" },
    { "LineCreation": true, "from": "step-2", "to": "step-3" },
    { "LineCreation": true, "from": "step-3", "to": "result" }
  ]
}"""

PEDAGOGY = """\
- ``code-title`` = figure description + given measurements (no coordinates from you).
- Boxes: list givens → state formula → substitute → compute → **last box = answer with units**.
- Name the shape and which formula applies (area, perimeter, Pythagoras, angle sum, etc.).
- Include units in every numeric box (cm, m², degrees) when the problem uses them.
- For proofs, each box is one logical claim (given, construction, conclusion)."""

SYSTEM = trunk_system_prompt(
    title="You design **geometry** diagrams (shapes, formulas, measurements).",
    layout_mode="math",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="math",
    subtype="geometry",
    layout_mode="math",
    system=SYSTEM,
    human_hint="Use the user's shape and numbers. Last box = measured result with units.",
    produce_line=f"Produce one geometry DrawingStage. {math_produce_line()}",
)
