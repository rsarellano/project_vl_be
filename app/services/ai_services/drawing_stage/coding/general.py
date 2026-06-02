"""Coding · general — fallback coding questions."""

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
      "text": ["// user's code", "..."],
      "portions": [{ "id": "main", "lines": [0, 1], "label": "Main" }]
    },
    { "id": "explain-main", "BoxCreation": true, "linkedPortion": "main", "text": ["Explain this", "block"] }
  ],
  "connections": []
}"""

PEDAGOGY = """\
- Prefer code-map with semantic portions and linked explanations.
- If the user pasted code, reproduce it exactly; otherwise provide a complete relevant solution."""

SYSTEM = code_map_system_prompt(
    title="You design **general coding** diagrams.",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="coding",
    subtype="general",
    layout_mode="code-map",
    system=SYSTEM,
    human_hint="Match the user's coding question.",
    produce_line=f"Produce a coding DrawingStage. {code_map_produce_line(pasted=False)}",
)
