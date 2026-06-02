"""Coding · code_solution — implement a full working solution."""

from app.services.ai_services.drawing_stage._prompt_types import SubtypePrompt
from app.services.ai_services.drawing_stage.coding._code_map_contract import (
    code_map_produce_line,
    code_map_system_prompt,
)

EXAMPLE = """{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "layoutMode": "code-map",
  "objects": [
    {
      "id": "source",
      "CodeDisplay": true,
      "language": "javascript",
      "text": ["function solve(nums, target) {", "  const seen = new Map();", "  ...", "}"],
      "portions": [
        { "id": "setup", "lines": [0, 1], "label": "Setup" },
        { "id": "loop", "lines": [2, 2], "label": "Scan" }
      ]
    },
    { "id": "explain-setup", "BoxCreation": true, "linkedPortion": "setup", "text": ["Why we need", "this structure"] },
    { "id": "explain-loop", "BoxCreation": true, "linkedPortion": "loop", "text": ["What each", "iteration does"] }
  ],
  "connections": []
}"""

PEDAGOGY = """\
- ``CodeDisplay.text`` = the **complete correct program** for the user's problem (every line needed to run).
- ``portions`` = logical blocks (setup, main loop, edge cases, return). Non-overlapping; cover all lines.
- Explanation boxes: **why** each block exists, not a line-by-line paraphrase of the code.
- Pick ``language`` from the user's request (javascript, python, typescript, etc.).
- Do not paste a famous template (e.g. Two Sum) unless the user asked for that exact problem."""

SYSTEM = code_map_system_prompt(
    title="You design **code solution** diagrams (implement & explain working code).",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="coding",
    subtype="code_solution",
    layout_mode="code-map",
    system=SYSTEM,
    human_hint="Implement the user's actual problem, not a different algorithm.",
    produce_line=f"Produce a code_solution DrawingStage. {code_map_produce_line(pasted=False)}",
)
