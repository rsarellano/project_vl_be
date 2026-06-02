"""Coding · loop_trace — trace loops iteration by iteration."""

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
      "text": ["for (let i = 0; i < 3; i++) {", "  console.log(i);", "}"],
      "portions": [
        { "id": "init", "lines": [0, 0], "label": "Init" },
        { "id": "check", "lines": [0, 0], "label": "Check" },
        { "id": "body", "lines": [1, 1], "label": "Body" },
        { "id": "inc", "lines": [0, 0], "label": "Increment" }
      ]
    },
    { "id": "explain-init", "BoxCreation": true, "linkedPortion": "init", "text": ["Inside the for-loop", "header: let i = 0", "i starts at 0"] },
    { "id": "explain-check", "BoxCreation": true, "linkedPortion": "check", "text": ["Condition: i < 3", "Must be true to", "enter the body"] },
    { "id": "explain-body", "BoxCreation": true, "linkedPortion": "body", "text": ["Body runs when", "condition is true", "console.log(i)"] },
    { "id": "explain-inc", "BoxCreation": true, "linkedPortion": "inc", "text": ["i++ runs after", "each body pass", "then re-check i < 3"] }
  ],
  "connections": []
}"""

PEDAGOGY = """\
- Put the **full loop program** in ``CodeDisplay.text`` (preserve every character: ``<``, ``>``, ``++``, etc.).
- Use **separate portions** for for-loop header concepts when tracing a ``for`` loop:
  - init (``let i = 0`` inside the header)
  - check (``i < n`` condition)
  - increment (``i++`` in the header)
  - body (loop body lines)
  Portions may reference the same header line index when needed; labels distinguish them.
- Each ``BoxCreation`` explanation must be **descriptive**, not telegraphic. Teach a beginner:
  - *Bad:* "i starts at 0"
  - *Good:* "Inside the for-loop parameter, let i = 0 — the counter starts at zero"
  - *Good:* "i < 3 — this condition must be true to enter the body; after each pass, i++ and the check runs again"
- Use 3–5 short lines per box (~18 chars per line). Name **what part of the loop** you mean (header vs body).
- For ``while`` loops, same idea: init before loop, condition line, body, update step."""

SYSTEM = code_map_system_prompt(
    title="You design **loop trace** diagrams (trace for/while execution).",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="coding",
    subtype="loop_trace",
    layout_mode="code-map",
    system=SYSTEM,
    human_hint=(
        "Use descriptive teaching prose in every explanation box (header vs body vs increment). "
        "Preserve all operators in CodeDisplay.text, especially < and >."
    ),
    produce_line=f"Produce a loop_trace DrawingStage. {code_map_produce_line(pasted=False)}",
)
