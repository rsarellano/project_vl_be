"""Science · chemistry — reactions, stoichiometry, bonding."""

from app.services.ai_services.drawing_stage._prompt_types import SubtypePrompt
from app.services.ai_services.drawing_stage._trunk_contract import science_produce_line, trunk_system_prompt

EXAMPLE = """{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "layoutMode": "science",
  "objects": [
    { "id": "topic", "TextCreation": true, "role": "code-title", "text": ["Combustion of methane"] },
    { "id": "objective", "TextCreation": true, "role": "objective", "text": ["Objective:", "Balance and", "explain reaction"] },
    { "id": "step-1", "BoxCreation": true, "text": ["Reactants", "", "CH₄ + O₂"] },
    { "id": "step-2", "BoxCreation": true, "text": ["Conditions", "", "Heat / spark", "Excess O₂"] },
    { "id": "step-3", "BoxCreation": true, "text": ["Products", "", "CO₂ + H₂O", "energy released"] },
    { "id": "result", "BoxCreation": true, "text": ["Balanced", "", "CH₄+2O₂→CO₂+2H₂O"] }
  ],
  "connections": [
    { "LineCreation": true, "from": "step-1", "to": "step-2" },
    { "LineCreation": true, "from": "step-2", "to": "step-3" },
    { "LineCreation": true, "from": "step-3", "to": "result" }
  ]
}"""

PEDAGOGY = """\
- ``code-title`` = reaction name or chemical question.
- Boxes: species/context → conditions (catalyst, temperature) → transformation → balanced equation or conclusion in **last box**.
- Show states (s), (l), (g), (aq) when the problem uses them.
- For stoichiometry: moles given → mole ratio → mass/volume result in separate boxes.
- Do not invent a different reaction than the user asked about."""

SYSTEM = trunk_system_prompt(
    title="You design **chemistry** diagrams (reactions and chemical reasoning).",
    layout_mode="science",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="science",
    subtype="chemistry",
    layout_mode="science",
    system=SYSTEM,
    human_hint="Use the user's species and reaction. Last box = balanced form or numeric result.",
    produce_line=f"Produce one chemistry DrawingStage. {science_produce_line()}",
)
