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
    {
      "id": "explain-setup",
      "BoxCreation": true,
      "linkedPortion": "setup",
      "text": ["Why we need", "this structure"],
      "derivation": {
        "fromStepId": "source",
        "beats": [
          { "type": "note", "text": "We prepare a lookup structure before scanning." },
          { "type": "expression", "text": "const seen = new Map();", "tokens": [
            { "lexeme": "const", "explain": "Declares a name that cannot be reassigned." },
            { "lexeme": "seen", "explain": "The lookup table we fill while scanning nums." },
            { "lexeme": "=", "explain": "Stores the new Map into seen." },
            { "lexeme": "new", "explain": "Creates a fresh object." },
            { "lexeme": "Map", "explain": "Key-value store so later lookups are O(1)." }
          ] },
          { "type": "arrow", "direction": "down" },
          { "type": "explain", "text": "Why: a Map lets each later value ask 'have I seen its complement?' in O(1)." },
          { "type": "explain", "text": "Without this table we would re-scan earlier numbers on every step." }
        ]
      }
    },
    {
      "id": "explain-loop",
      "BoxCreation": true,
      "linkedPortion": "loop",
      "text": ["What each", "iteration does"],
      "derivation": {
        "fromStepId": "explain-setup",
        "beats": [
          { "type": "note", "text": "Each iteration checks one number against what we already stored." },
          { "type": "expression", "text": "for (const n of nums) { ... }" },
          { "type": "arrow", "direction": "down" },
          { "type": "explain", "text": "Compute need = target - n, then look it up in seen." },
          { "type": "explain", "text": "If found, return the pair; otherwise store n and continue." }
        ]
      }
    },
    {
      "id": "answer",
      "BoxCreation": true,
      "AnswerBox": true,
      "text": ["Example 1 → [0, 1]", "O(n) time, O(n) space"]
    }
  ],
  "connections": []
}"""

PEDAGOGY = """\
- ``CodeDisplay.text`` = the **complete correct program** for the user's problem, at most 100 lines.
  Write the core solution only. Do not add extra files, a demo harness, or unused helpers.
- Never put the problem statement, examples, or constraints into ``CodeDisplay``.
- ``portions`` = logical blocks (setup, main loop, edge cases, return). Non-overlapping; cover all lines.
- Explanation boxes: **why** each block exists, not a line-by-line paraphrase of the code.
- Also emit one bottom answer card:
  ``{"id":"answer","BoxCreation":true,"AnswerBox":true,"text":["Example 1 → …","O(…) complexity"]}``
  (no ``linkedPortion``). First-example result + time/space complexity.
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
