"""Math · arithmetic — operations, fractions, percents, number sense, order of ops."""

from __future__ import annotations

import re

from app.services.ai_services.drawing_stage._prompt_types import SubtypePrompt
from app.services.ai_services.drawing_stage._trunk_contract import math_produce_line, math_trunk_system_prompt

# Simple two-operand pattern (no parentheses / mixed ops beyond one operator).
_SIMPLE_TWO_OPERAND = re.compile(
    r"^\s*\d+(?:\.\d+)?\s*[+\-×*÷/]\s*\d+(?:\.\d+)?\s*(?:=\s*\?)?\s*$"
)

EXAMPLE = """{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "layoutMode": "math",
  "objects": [
    { "id": "problem", "TextCreation": true, "role": "code-title", "text": ["5 + 3(23 - 2) - 4 / 6 = ?"] },
    { "id": "objective", "TextCreation": true, "role": "objective", "text": ["Objective:", "Use MDAS order of operations"] },
    {
      "id": "step-1",
      "BoxCreation": true,
      "text": ["Parentheses first", "", "23 - 2 = 21"],
      "derivation": {
        "fromStepId": "problem",
        "beats": [
          { "type": "note", "text": "We start from the original expression." },
          { "type": "expression", "text": "5 + 3(23 - 2) - 4 / 6" },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "Parentheses first (MDAS)." },
          { "type": "explain", "text": "Why: parentheses are evaluated before multiply, divide, add, or subtract." },
          { "type": "explain", "text": "Inside the parentheses: 23 - 2 = 21." },
          { "type": "motion_stage", "from": "23 - 2", "to": "21" },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "After this step:" },
          { "type": "expression", "text": "5 + 3(21) - 4 / 6" }
        ]
      }
    },
    {
      "id": "step-2",
      "BoxCreation": true,
      "text": ["Multiply", "", "3 × 21 = 63"],
      "derivation": {
        "fromStepId": "step-1",
        "beats": [
          { "type": "note", "text": "We start from the previous step." },
          { "type": "expression", "text": "5 + 3(21) - 4 / 6" },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "Next: multiplication (before + and -)." },
          { "type": "explain", "text": "Why: multiplication and division come before addition and subtraction." },
          { "type": "explain", "text": "3(21) means 3 × 21 = 63." },
          { "type": "motion_stage", "from": "3 × 21", "to": "63" },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "After this step:" },
          { "type": "expression", "text": "5 + 63 - 4 / 6" }
        ]
      }
    },
    {
      "id": "step-3",
      "BoxCreation": true,
      "text": ["Divide", "", "4 / 6 = 2/3"],
      "derivation": {
        "fromStepId": "step-2",
        "beats": [
          { "type": "note", "text": "We start from the previous step." },
          { "type": "expression", "text": "5 + 63 - 4 / 6" },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "Next: division (same priority as multiply, left to right)." },
          { "type": "explain", "text": "Why: 4 / 6 must be done before the remaining + and -." },
          { "type": "explain", "text": "4 / 6 simplifies to 2/3." },
          { "type": "motion_stage", "from": "4 / 6", "to": "2/3" },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "After this step:" },
          { "type": "expression", "text": "5 + 63 - 2/3" }
        ]
      }
    },
    {
      "id": "step-4",
      "BoxCreation": true,
      "text": ["Add", "", "5 + 63 = 68"],
      "derivation": {
        "fromStepId": "step-3",
        "beats": [
          { "type": "note", "text": "We start from the previous step." },
          { "type": "expression", "text": "5 + 63 - 2/3" },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "Addition and subtraction left to right: add first." },
          { "type": "explain", "text": "Why: + and - have the same priority, so work left to right." },
          { "type": "motion_stage", "from": "5 + 63", "to": "68" },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "After this step:" },
          { "type": "expression", "text": "68 - 2/3" }
        ]
      }
    },
    {
      "id": "step-5",
      "BoxCreation": true,
      "text": ["Subtract", "", "68 - 2/3 = 202/3"],
      "derivation": {
        "fromStepId": "step-4",
        "beats": [
          { "type": "note", "text": "We start from the previous step." },
          { "type": "expression", "text": "68 - 2/3" },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "Finish with subtraction." },
          { "type": "explain", "text": "68 = 204/3, so 204/3 - 2/3 = 202/3." },
          { "type": "motion_stage", "from": "68 - 2/3", "to": "202/3" },
          { "type": "arrow", "direction": "down" },
          { "type": "note", "text": "After this step:" },
          { "type": "expression", "text": "202/3" }
        ]
      }
    },
    { "id": "result", "BoxCreation": true, "text": ["Answer", "", "202/3"] }
  ],
  "connections": [
    { "LineCreation": true, "from": "step-1", "to": "step-2" },
    { "LineCreation": true, "from": "step-2", "to": "step-3" },
    { "LineCreation": true, "from": "step-3", "to": "step-4" },
    { "LineCreation": true, "from": "step-4", "to": "step-5" },
    { "LineCreation": true, "from": "step-5", "to": "result" }
  ]
}"""

PEDAGOGY = """\
- ``code-title`` = the numeric question (expression or word problem summary).
- Keep numbers explicit in every step; do not jump from question to answer in one box.
- **Last box = final numeric answer** (``Answer``).

### Shape A — simple two-operand problems (e.g. ``5 + 3``, ``12 ÷ 4``)
Use this short pipeline only when there is **one** operator and **two** numbers:
1. ``Given Values`` — the two numbers (no ``derivation``).
2. ``Applied Operation`` — name **one** op only (e.g. ``Addition``) + a short subtitle. \
**Never** list every MDAS operation in one line (that overflows the box). **No ``derivation``** \
(the frontend shows a one-line why note).
3. ``Calculation`` — expression and result, with a short ``derivation``:
   ``expression`` → ``motion_stage`` (from expression → result) → ``expression`` (result).
4. ``Answer`` — final value.

### Shape B — order of operations / MDAS / PEMDAS (REQUIRED for mixed ops)
When the expression has **parentheses**, **implied multiply** like ``3(21)``, or **more than one \
operator** (e.g. ``5 + 3(23 - 2) - 4 / 6``), do **NOT** use Given Values / Applied Operation.

Instead: **one box per MDAS move**, in order:
1. Parentheses (innermost first)
2. Exponents (if any)
3. Multiply / Divide left to right
4. Add / Subtract left to right
5. Final ``Answer`` box

Rules for Shape B:
- Each transform box title names the move (``Parentheses first``, ``Multiply``, ``Divide``, ``Add``, …).
- Box text shows the **local** computation that step finishes (e.g. ``23 - 2 = 21``), not only prose.
- Every transform box MUST include ``derivation.beats`` following the Layer 2 script:
  start note → full current expression → arrow → what we're doing → \
  ``Why: …`` explain (MDAS reason) → mechanic explain → ``motion_stage`` for the local op → \
  arrow → ``After this step:`` → **full rewritten expression** (or final value on the last transform).
- ``motion_stage.from`` / ``to`` are the **local** bit changing (e.g. ``23 - 2`` → ``21``), not the whole line.
- Never collapse several MDAS moves into one ``Calculation`` box.
- Prefer exact fractions over messy decimals when division does not divide evenly.

### Fractions / percents / word problems
- One box per conversion or common-denominator step; last box = final value.
- Word problems: first box may restate known quantities, then compute with Shape A or B as needed."""

SYSTEM = math_trunk_system_prompt(
    title="You design **arithmetic** diagrams (numeric operations and order of operations).",
    example_json=EXAMPLE,
    pedagogy=PEDAGOGY,
)

PROMPT = SubtypePrompt(
    domain="math",
    subtype="arithmetic",
    layout_mode="math",
    system=SYSTEM,
    human_hint=(
        "Numeric only — no variables. "
        "Simple two-operand → Given Values, Applied Operation, Calculation, Answer. "
        "Mixed ops / parentheses / MDAS → one box per order-of-operations move with derivation "
        "(start → why → motion_stage → rewritten expression). Last box = Answer."
    ),
    produce_line=f"Produce one arithmetic DrawingStage. {math_produce_line()}",
)


def looks_like_order_of_operations(prompt: str) -> bool:
    """True when the prompt needs multi-step MDAS rather than a single calculation."""
    text = (prompt or "").strip()
    if not text:
        return False
    # Strip a trailing "= ?" style ask so we inspect the expression itself.
    expr = re.sub(r"=\s*\?\s*$", "", text).strip()
    if _SIMPLE_TWO_OPERAND.match(expr):
        return False
    has_parens = "(" in expr or ")" in expr
    # Count distinct operator occurrences (including juxtaposition like 3(21)).
    op_hits = len(re.findall(r"[+\-×*÷/]", expr))
    juxtaposition = bool(re.search(r"\d\s*\(", expr))
    return has_parens or juxtaposition or op_hits >= 2
