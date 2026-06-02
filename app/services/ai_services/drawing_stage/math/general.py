"""Math · general — fallback when subtype is unclear."""

from app.services.ai_services.drawing_stage._prompt_types import SubtypePrompt
from app.services.ai_services.drawing_stage._trunk_contract import math_produce_line, trunk_system_prompt

EXAMPLE = """{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "layoutMode": "math",
  "objects": [
    { "id": "problem", "TextCreation": true, "role": "code-title", "text": ["Math problem"] },
    { "id": "objective", "TextCreation": true, "role": "objective", "text": ["Objective:", "Solve step by step"] },
    { "id": "step-1", "BoxCreation": true, "text": ["Step 1", "", "Identify givens"] },
    { "id": "step-2", "BoxCreation": true, "text": ["Step 2", "", "Apply method"] },
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
- Last box = final answer the user asked for."""

SYSTEM = trunk_system_prompt(
    title="You design **general math** diagrams.",
    layout_mode="math",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="math",
    subtype="general",
    layout_mode="math",
    system=SYSTEM,
    human_hint="Choose a step breakdown that matches the user's question.",
    produce_line=f"Produce one math DrawingStage. {math_produce_line()}",
)
