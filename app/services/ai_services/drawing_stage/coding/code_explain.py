"""Coding · code_explain — user pasted code to understand (not replace)."""

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
      "language": "typescript",
      "text": ["interface User {", "  id: string;", "  name: string;", "}"],
      "portions": [
        { "id": "decl", "lines": [0, 0], "label": "Header" },
        { "id": "fields", "lines": [1, 2], "label": "Fields" }
      ]
    },
    { "id": "explain-decl", "BoxCreation": true, "linkedPortion": "decl", "text": ["Declares a", "User type"] },
    { "id": "explain-fields", "BoxCreation": true, "linkedPortion": "fields", "text": ["id and name", "properties"] }
  ],
  "connections": []
}"""

PEDAGOGY = """\
- ``CodeDisplay.text`` MUST be the **user's pasted snippet verbatim** (one string per line, keep indentation).
- Do **not** replace with findMax, twoSum, or other tutorial code.
- ``portions`` follow **their** structure: declarations, fields, methods, branches, returns.
- Explanation boxes describe what **this** code means in plain language.
- If the human message includes a fenced code block, that block is the source of truth."""

SYSTEM = code_map_system_prompt(
    title="You design **code explain** diagrams (teach existing pasted code).",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="coding",
    subtype="code_explain",
    layout_mode="code-map",
    system=SYSTEM,
    human_hint="Never substitute different code. Explain only what the user pasted.",
    produce_line=f"Produce a code_explain DrawingStage. {code_map_produce_line(pasted=True)}",
)
