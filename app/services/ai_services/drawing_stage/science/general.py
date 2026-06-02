"""Science · general — fallback for science questions."""

from app.services.ai_services.drawing_stage._prompt_types import SubtypePrompt
from app.services.ai_services.drawing_stage._trunk_contract import science_produce_line, trunk_system_prompt

EXAMPLE = """{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "layoutMode": "science",
  "objects": [
    { "id": "topic", "TextCreation": true, "role": "code-title", "text": ["Science question"] },
    { "id": "objective", "TextCreation": true, "role": "objective", "text": ["Objective:", "Explain clearly"] },
    { "id": "step-1", "BoxCreation": true, "text": ["Context", "", "Setup"] },
    { "id": "step-2", "BoxCreation": true, "text": ["Process", "", "Main idea"] },
    { "id": "result", "BoxCreation": true, "text": ["Conclusion", "", "Takeaway"] }
  ],
  "connections": [
    { "LineCreation": true, "from": "step-1", "to": "step-2" },
    { "LineCreation": true, "from": "step-2", "to": "result" }
  ]
}"""

PEDAGOGY = """\
- Use context → mechanism/process → evidence/observation → conclusion when applicable.
- Match vocabulary to the user's topic (earth science, astronomy, etc.).
- Last box = clear takeaway."""

SYSTEM = trunk_system_prompt(
    title="You design **general science** diagrams.",
    layout_mode="science",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="science",
    subtype="general",
    layout_mode="science",
    system=SYSTEM,
    human_hint="Pick a process sequence that fits the user's science question.",
    produce_line=f"Produce one science DrawingStage. {science_produce_line()}",
)
