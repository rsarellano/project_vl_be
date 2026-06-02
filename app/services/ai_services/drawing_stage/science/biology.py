"""Science · biology — cells, organisms, pathways, ecosystems."""

from app.services.ai_services.drawing_stage._prompt_types import SubtypePrompt
from app.services.ai_services.drawing_stage._trunk_contract import science_produce_line, trunk_system_prompt

EXAMPLE = """{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "layoutMode": "science",
  "objects": [
    { "id": "topic", "TextCreation": true, "role": "code-title", "text": ["Photosynthesis"] },
    { "id": "objective", "TextCreation": true, "role": "objective", "text": ["Objective:", "Trace inputs,", "process, outputs"] },
    { "id": "step-1", "BoxCreation": true, "text": ["Where", "", "Chloroplasts", "in leaf cells"] },
    { "id": "step-2", "BoxCreation": true, "text": ["Inputs", "", "CO₂, H₂O", "light energy"] },
    { "id": "step-3", "BoxCreation": true, "text": ["Process", "", "Light reactions", "Calvin cycle"] },
    { "id": "result", "BoxCreation": true, "text": ["Outputs", "", "Glucose + O₂"] }
  ],
  "connections": [
    { "LineCreation": true, "from": "step-1", "to": "step-2" },
    { "LineCreation": true, "from": "step-2", "to": "step-3" },
    { "LineCreation": true, "from": "step-3", "to": "result" }
  ]
}"""

PEDAGOGY = """\
- ``code-title`` = process, structure, or phenomenon name.
- Boxes: biological context (organ/cell/system) → inputs/requirements → mechanism/pathway → outcome/function.
- Use accurate terms (organelle names, molecules, stages of mitosis, etc.) at the user's level.
- For comparisons (plant vs animal), dedicate boxes to each side before a summary box.
- Last box = functional takeaway or products of the process."""

SYSTEM = trunk_system_prompt(
    title="You design **biology** diagrams (living systems and processes).",
    layout_mode="science",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="science",
    subtype="biology",
    layout_mode="science",
    system=SYSTEM,
    human_hint="Stay on the user's biological topic. Name structures and molecules correctly.",
    produce_line=f"Produce one biology DrawingStage. {science_produce_line()}",
)
