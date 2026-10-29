"""Math · calculus — Calculus 1 limits, continuity, derivatives, tangent lines."""

from app.services.ai_services.drawing_stage._prompt_types import SubtypePrompt
from app.services.ai_services.drawing_stage._trunk_contract import math_produce_line, math_trunk_system_prompt

EXAMPLE = """{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "layoutMode": "math",
  "objects": [
    { "id": "problem", "TextCreation": true, "role": "code-title", "text": ["lim x -> 3", "x^2 + 5x - 4"] },
    { "id": "objective", "TextCreation": true, "role": "objective", "text": ["Objective:", "Evaluate the limit"] },
    {
      "id": "step-1",
      "BoxCreation": true,
      "text": ["Direct substitution", "", "Polynomial, defined at 3"],
      "derivation": {
        "fromStepId": "problem",
        "beats": [
          { "type": "note", "text": "We start from the original limit." },
          { "type": "expression", "text": "lim x -> 3 (x^2 + 5x - 4)" },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "A polynomial is continuous everywhere." },
          { "type": "explain", "text": "Why substitution works: x^2 + 5x - 4 is defined at x = 3, so the limit equals the function value there." },
          { "type": "explain", "text": "Keep every term. Do not drop x^2, and do not rewrite this as a simplify-like-terms problem." }
        ]
      }
    },
    {
      "id": "step-2",
      "BoxCreation": true,
      "text": ["Substitute x = 3", "", "3^2 + 5(3) - 4"],
      "derivation": {
        "fromStepId": "step-1",
        "beats": [
          { "type": "note", "text": "We start from the previous step." },
          { "type": "expression", "text": "lim x -> 3 (x^2 + 5x - 4)" },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "Replace x with 3 in every term." },
          { "type": "explain", "text": "x^2 becomes 3^2, 5x becomes 5(3), and the constant -4 stays -4." },
          { "type": "expression", "text": "3^2 + 5(3) - 4" }
        ]
      }
    },
    {
      "id": "result",
      "BoxCreation": true,
      "text": ["Limit", "", "20"],
      "derivation": {
        "fromStepId": "step-2",
        "beats": [
          { "type": "note", "text": "We start from the previous step." },
          { "type": "expression", "text": "9 + 15 - 4" },
          { "type": "arrow", "direction": "down" },
          { "type": "explain", "text": "3^2 = 9 and 5(3) = 15. Then 9 + 15 - 4 = 20." },
          { "type": "expression", "text": "20" }
        ]
      }
    }
  ],
  "connections": [
    { "LineCreation": true, "from": "step-1", "to": "step-2" },
    { "LineCreation": true, "from": "step-2", "to": "result" }
  ]
}"""

PEDAGOGY = """\
- ``code-title`` = the full calculus statement. For a limit, line 1 is ``lim x -> a`` and line 2 is the \
whole expression, including every power (``x^2``). Never shorten it to the last terms only.
- ``objective`` names the calculus task: evaluate the limit, differentiate, or find the tangent line. \
Never use ``Simplify the expression`` for a limit or a derivative.
- Plain math only in box text and beats: ``lim x -> 3``, ``x^2``, ``d/dx``, ``f'(x)``. No LaTeX commands.
- Last box is the value or the derivative the learner asked for.

### Limits
- Polynomial or other function defined at the point: say why substitution is valid, substitute, then arithmetic. \
Example: ``lim x -> 3 (x^2 + 5x - 4) = 20``.
- If substitution gives 0/0, do not stop. Factor, cancel, or rationalize, then substitute the simplified expression.
- One-sided limits: compute from the named side and say if the two-sided limit exists.
- Limits at infinity: divide by the highest power and state the end value (or that it diverges).

### Derivatives
- Name the rule before using it (power, sum, product, quotient, or chain).
- Show the rewrite, not only the final derivative. Power rule: ``d/dx (x^n) = n x^(n-1)``.
- Last box = ``f'(x)`` or the requested derivative.
- Tangent line: derivative at the point, then point-slope form ``y - y1 = m(x - x1)``.

### Do not
- Do not drop the limit symbol, the approach value, or any term such as ``x^2``.
- Do not group like terms unless that is a step inside an indeterminate limit after you have said why.
- Integrals, related rates, and optimization are out of scope. If asked, still show the closest limit or derivative step you can, and say that application is not in this diagram."""

SYSTEM = math_trunk_system_prompt(
    title="You design **Calculus 1** diagrams (limits, continuity, derivatives, tangent lines).",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="math",
    subtype="calculus",
    layout_mode="math",
    system=SYSTEM,
    human_hint=(
        "This is Calculus 1, not an algebra simplify problem. "
        "Keep the full limit or derivative in the title, including every power. "
        "For a polynomial limit, substitute and compute the number. "
        "For a derivative, name the rule and show the rewrite. "
        "Include derivation.beats on every step that changes the math."
    ),
    produce_line=f"Produce one calculus DrawingStage. {math_produce_line()}",
)
