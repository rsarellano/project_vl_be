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
    { "id": "step-1", "BoxCreation": true, "text": ["Given Values", "", "5 and 3"] },
    { "id": "step-2", "BoxCreation": true, "text": ["Applied Operation", "", "Addition", "Combine the values"] },
    {
      "id": "step-3",
      "BoxCreation": true,
      "text": ["Calculation", "", "5 + 3", "= 8"],
      "derivation": {
        "fromStepId": "step-2",
        "beats": [
          { "type": "expression", "text": "5 + 3" },
          { "type": "motion_stage", "from": "5 + 3", "to": "8" },
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
- Boxes: identify given values → name applied operation → show calculation → **last box = final value**.
- For word problems, first box may restate what is known before computing.
- For fractions/decimals/percents, one box per conversion or common-denominator step.
- Keep numbers explicit in every step; do not jump from question to answer in one box.

### Derivation rules for arithmetic
- **Only the Calculation step** gets a ``derivation``. The Given Values and Applied Operation \
steps do NOT get derivation — they are self-explanatory.
- The Calculation derivation has exactly 3 beats: \
``expression`` (the arithmetic expression), ``motion_stage`` with ``from``/``to``, \
and ``expression`` (the result). All pure math, zero prose.
- The ``motion_stage.from`` MUST be a pure arithmetic expression like ``5 + 3``, NOT prose. \
The ``motion_stage.to`` MUST be the numeric answer only. No ``operation`` key needed."""

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
        "Only the Calculation step gets derivation — 3 beats: expression, motion_stage, expression. "
        "No derivation on Given Values or Applied Operation boxes."
    ),
    produce_line=f"Produce one arithmetic DrawingStage. {math_produce_line()}",
)
