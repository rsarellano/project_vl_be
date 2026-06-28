"""Math · arithmetic — operations, fractions, percents, number sense."""

from app.services.ai_services.drawing_stage._prompt_types import SubtypePrompt
from app.services.ai_services.drawing_stage._trunk_contract import math_produce_line, math_trunk_system_prompt

EXAMPLE = """{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "layoutMode": "math",
  "objects": [
    { "id": "problem", "TextCreation": true, "role": "code-title", "text": ["5 + 3 = ?"] },
    { "id": "objective", "TextCreation": true, "role": "objective", "text": ["Objective:", "Add whole numbers"] },
    { "id": "step-1", "BoxCreation": true, "text": ["Operands", "", "5 and 3"] },
    { "id": "step-2", "BoxCreation": true, "text": ["Operation", "", "Addition", "Combine amounts"] },
    {
      "id": "step-3",
      "BoxCreation": true,
      "text": ["Work", "", "5 + 3", "= 8"],
      "derivation": {
        "fromStepId": "step-2",
        "beats": [
          { "type": "note", "text": "We start from the previous step." },
          { "type": "expression", "text": "5 + 3" },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "Add the operands." },
          {
            "type": "explain",
            "text": "Addition combines the two amounts: start at 5 and count up 3 more to reach 8."
          },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "After adding:" },
          { "type": "expression", "text": "8" }
        ]
      }
    },
    { "id": "result", "BoxCreation": true, "text": ["Answer", "", "5 + 3 = 8"] }
  ],
  "connections": [
    { "LineCreation": true, "from": "step-1", "to": "step-2" },
    { "LineCreation": true, "from": "step-2", "to": "step-3" },
    { "LineCreation": true, "from": "step-3", "to": "result" }
  ]
}"""

PEDAGOGY = """\
- ``code-title`` = the numeric question (expression or word problem summary).
- Boxes: identify operands → name operation → show calculation → **last box = final value**.
- For word problems, first box may restate what is known before computing.
- For fractions/decimals/percents, one box per conversion or common-denominator step.
- Keep numbers explicit in every step; do not jump from question to answer in one box.
- Include ``derivation.beats`` on calculation steps — explain WHY that operation applies (e.g. common denominator, place value)."""

SYSTEM = math_trunk_system_prompt(
    title="You design **arithmetic** diagrams (operations and numeric reasoning).",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="math",
    subtype="arithmetic",
    layout_mode="math",
    system=SYSTEM,
    human_hint=(
        "Show both operands before the operation. Last box = final numeric answer. "
        "Include derivation.beats on work steps."
    ),
    produce_line=f"Produce one arithmetic DrawingStage. {math_produce_line()}",
)
