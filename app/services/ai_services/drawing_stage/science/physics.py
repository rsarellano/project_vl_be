"""Science · physics — forces, motion, energy, formulas."""

from app.services.ai_services.drawing_stage._prompt_types import SubtypePrompt
from app.services.ai_services.drawing_stage._trunk_contract import science_produce_line, trunk_system_prompt

EXAMPLE = """{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "layoutMode": "science",
  "objects": [
    { "id": "topic", "TextCreation": true, "role": "code-title", "text": ["Object 2 kg", "pushed 3 m", "F = 10 N"] },
    { "id": "objective", "TextCreation": true, "role": "objective", "text": ["Objective:", "Find work done"] },
    { "id": "step-1", "BoxCreation": true, "text": ["Known", "", "F = 10 N", "d = 3 m"] },
    { "id": "step-2", "BoxCreation": true, "text": ["Formula", "", "W = F × d"] },
    { "id": "step-3", "BoxCreation": true, "text": ["Substitute", "", "W = 10×3", "= 30 J"] },
    { "id": "result", "BoxCreation": true, "text": ["Answer", "", "Work = 30 J"] }
  ],
  "connections": [
    { "LineCreation": true, "from": "step-1", "to": "step-2" },
    { "LineCreation": true, "from": "step-2", "to": "step-3" },
    { "LineCreation": true, "from": "step-3", "to": "result" }
  ]
}"""

PEDAGOGY = """\
- ``code-title`` = scenario with quantities (include units in text lines).
- Boxes: list givens with symbols → state law/formula → substitute → numeric result in **last box with units**.
- For motion: distinguish position, velocity, acceleration steps.
- For forces: free-body concepts in words (not coordinates) before summing forces.
- Keep SI units consistent (N, J, m/s, kg)."""

SYSTEM = trunk_system_prompt(
    title="You design **physics** diagrams (laws, quantities, calculations).",
    layout_mode="science",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="science",
    subtype="physics",
    layout_mode="science",
    system=SYSTEM,
    human_hint="Use the user's values and units. Last box = computed quantity with units.",
    produce_line=f"Produce one physics DrawingStage. {science_produce_line()}",
)
