"""Math · general — fallback when subtype is unclear."""

from app.services.ai_services.drawing_stage._prompt_types import SubtypePrompt
from app.services.ai_services.drawing_stage._trunk_contract import math_produce_line, math_trunk_system_prompt

EXAMPLE = """{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "layoutMode": "math",
  "objects": [
    { "id": "problem", "TextCreation": true, "role": "code-title", "text": ["Math problem"] },
    { "id": "objective", "TextCreation": true, "role": "objective", "text": ["Objective:", "Solve step by step"] },
    { "id": "step-1", "BoxCreation": true, "text": ["Step 1", "", "Identify givens"] },
    {
      "id": "step-2",
      "BoxCreation": true,
      "text": ["Step 2", "", "Apply method"],
      "derivation": {
        "fromStepId": "step-1",
        "beats": [
          { "type": "note", "text": "We start from the previous step." },
          { "type": "expression", "text": "givens from step 1" },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "Apply the method." },
          {
            "type": "explain",
            "text": "Explain why this method fits the givens and what it lets us find next."
          },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "After this step:" },
          { "type": "expression", "text": "intermediate result" }
        ]
      }
    },
    { "id": "result", "BoxCreation": true, "text": ["Result", "", "Final answer here"] }
  ],
  "connections": [
    { "LineCreation": true, "from": "step-1", "to": "step-2" },
    { "LineCreation": true, "from": "step-2", "to": "result" }
  ]
}"""

PEDAGOGY = """\
- Pick the clearest step sequence for the user's topic (even if mixed: word problem → equation → solve).
- Each box shows **one** idea or transformation; include numeric/symbolic state when relevant.
- Last box = final answer the user asked for.
- Every step that changes the math must include ``derivation.beats`` with problem-specific WHY text."""

SYSTEM = math_trunk_system_prompt(
    title="You design **general math** diagrams.",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="math",
    subtype="general",
    layout_mode="math",
    system=SYSTEM,
    human_hint="Choose a step breakdown that matches the user's question. Include derivation on each transform step.",
    produce_line=f"Produce one math DrawingStage. {math_produce_line()}",
)
