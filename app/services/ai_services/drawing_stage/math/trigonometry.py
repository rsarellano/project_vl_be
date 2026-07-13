"""Math · trigonometry — right-triangle SOH CAH TOA, inverse trig."""

from app.services.ai_services.drawing_stage._prompt_types import SubtypePrompt
from app.services.ai_services.drawing_stage._trunk_contract import math_produce_line, math_trunk_system_prompt

EXAMPLE = """{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "layoutMode": "math",
  "objects": [
    { "id": "problem", "TextCreation": true, "role": "code-title", "text": ["Right triangle", "hypotenuse = 10", "angle = 30°", "Find the opposite side"] },
    { "id": "objective", "TextCreation": true, "role": "objective", "text": ["Objective:", "Find the missing side using trigonometry"] },
    {
      "id": "step-1",
      "BoxCreation": true,
      "text": ["Identify knowns", "", "θ = 30°, H = 10, x = ?"],
      "derivation": {
        "beats": [
          { "type": "note", "text": "Draw the right triangle and label the sides:" },
          {
            "type": "trig_scene",
            "angle": 30,
            "hypotenuseLabel": "10",
            "oppositeLabel": "x (Unknown)",
            "adjacentLabel": "Adjacent",
            "unknownSide": "opposite",
            "ratio": "sin",
            "formula": "\\\\sin(θ) = Opposite / Hypotenuse"
          },
          {
            "type": "explain",
            "text": "Why we use Sine: We want the Opposite side and we know the Hypotenuse. Sine = Opposite / Hypotenuse (SOH) connects what we want with what we know."
          }
        ]
      }
    },
    {
      "id": "step-2",
      "BoxCreation": true,
      "text": "sin(30°) = x/10",
      "derivation": {
        "beats": [
          { "type": "note", "text": "Set up the equation using the sine ratio:" },
          { "type": "explain", "text": "We have the Opposite (x) and the Hypotenuse (10), so we use SOH: sin(θ) = Opposite / Hypotenuse." },
          { "type": "expression", "text": "sin(30°) = x/10" }
        ]
      }
    },
    {
      "id": "step-3",
      "BoxCreation": true,
      "text": "x = 10 × sin(30°)",
      "derivation": {
        "beats": [
          { "type": "note", "text": "Multiply both sides by 10:" },
          {
            "type": "motion_stage",
            "from": "sin(30°) = x/10",
            "to": "x = 10 × sin(30°)",
            "operation": "× 10"
          }
        ]
      }
    },
    {
      "id": "step-4",
      "BoxCreation": true,
      "text": "x = 5",
      "derivation": {
        "beats": [
          { "type": "note", "text": "Evaluate sin(30°) = 0.5:" },
          { "type": "expression", "text": "x = 10 × 0.5" },
          { "type": "arrow", "direction": "down" },
          { "type": "expression", "text": "x = 5" },
          {
            "type": "trig_scene",
            "angle": 30,
            "hypotenuseLabel": "10",
            "oppositeLabel": "5 ✓",
            "adjacentLabel": "Adjacent",
            "solution": "x = 5 units"
          }
        ]
      }
    }
  ],
  "connections": [
    { "LineCreation": true, "from": "step-1", "to": "step-2" },
    { "LineCreation": true, "from": "step-2", "to": "step-3" },
    { "LineCreation": true, "from": "step-3", "to": "step-4" }
  ]
}"""

PEDAGOGY = """\
- ``code-title`` = the triangle description + given values + what to find.
- **Step 1 — Identify knowns:** list given values (angle, sides) and the unknown. \
Include a ``trig_scene`` beat in the derivation with labeled sides. Set ``unknownSide`` \
to ``"opposite"``, ``"adjacent"``, or ``"hypotenuse"`` to visually highlight it. Set \
``ratio`` to ``"sin"``, ``"cos"``, or ``"tan"`` to highlight the two relevant sides.
- **Step 2 — Set up equation:** explain WHY that ratio was chosen (SOH CAH TOA). Start \
the explain beat with "Why" so the panel shows it as a highlighted reason callout. Show \
the equation with actual values substituted.
- **Step 3+ — Solve:** isolate the unknown, compute the result.
- **Final step:** include a ``trig_scene`` beat with the ``solution`` field showing the \
solved triangle with all sides labeled.
- **Inverse trig (finding an angle):** when the angle is unknown and two sides are given, \
use ``angleLabel: "θ = ?"`` on the ``trig_scene`` beat. The solve steps should use \
arcsin/arccos/arctan. Set ``unknownSide`` to ``null`` since no side is unknown.

### ``trig_scene`` beat reference

```json
{
  "type": "trig_scene",
  "angle": 30,
  "angleLabel": "30°",
  "hypotenuseLabel": "10",
  "oppositeLabel": "x (Unknown)",
  "adjacentLabel": "Adjacent",
  "unknownSide": "opposite",
  "ratio": "sin",
  "formula": "\\\\sin(θ) = Opposite / Hypotenuse",
  "solution": "x = 5 units"
}
```

Fields:
- ``angle`` (number): the acute angle in degrees (used to draw the triangle shape).
- ``angleLabel`` (string, optional): text shown next to the angle arc. Defaults to \
``"<angle>°"``. Use ``"θ = ?"`` when the angle is unknown.
- ``hypotenuseLabel``, ``oppositeLabel``, ``adjacentLabel`` (string): labels for each side.
- ``unknownSide`` (string, optional): ``"hypotenuse"``, ``"opposite"``, or ``"adjacent"`` — \
renders that side as dashed.
- ``ratio`` (string, optional): ``"sin"``, ``"cos"``, or ``"tan"`` — highlights the two \
relevant sides with emphasis colors, dims the third.
- ``formula`` (string, optional): shown as a KaTeX card beneath the triangle.
- ``solution`` (string, optional): shown as a green result card beneath the triangle.

### Choosing the ratio (SOH CAH TOA)

Always explain WHY the chosen ratio is correct:
- **sin** (SOH): connects Opposite and Hypotenuse — use when those are the known/unknown pair.
- **cos** (CAH): connects Adjacent and Hypotenuse — use when those are the known/unknown pair.
- **tan** (TOA): connects Opposite and Adjacent — use when those are the known/unknown pair.

### Use actual degree symbols

Use the actual ``°`` character, not ``\\circ``. The frontend handles conversion automatically."""

SYSTEM = math_trunk_system_prompt(
    title="You design **trigonometry** diagrams (right-triangle SOH CAH TOA, inverse trig).",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="math",
    subtype="trigonometry",
    layout_mode="math",
    system=SYSTEM,
    human_hint=(
        "Use SOH CAH TOA to select the correct ratio. "
        "Step 1 must include a trig_scene beat with the triangle diagram. "
        "Explain WHY that ratio was chosen. "
        "Final step should include a trig_scene with the solution. "
        "Include derivation.beats on every step."
    ),
    produce_line=f"Produce one trigonometry DrawingStage. {math_produce_line()}",
)
