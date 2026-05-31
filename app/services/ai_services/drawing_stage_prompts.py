"""LLM system + human prompts for structured ``DrawingStage`` generation.

Contract
--------
The model is **locked to flag-driven mode**. It never picks coordinates,
sizes, animation timing, or connector geometry. The frontend owns every
spatial value (see ``boxCreation.tsx`` / ``textCreation.tsx`` /
``lineCreation.tsx``).

What the model emits
--------------------
A single JSON object in flag-driven ``DrawingStage`` shape::

    {
      "width": 1400,
      "height": 1250,
      "background": "#ffffff",
      "objects": [
        { "id": ..., "TextCreation": true, "role": "code-title" | "objective" | "console", "text": ... },
        { "id": ..., "BoxCreation": true,  "text": [ ... ] }
      ],
      "connections": [
        { "LineCreation": true, "from": <boxId>, "to": <boxId> }
      ]
    }

Editing tips
------------
Tighten the role examples here when you want stricter step-by-step traces.
"""

from app.services.ai_services.pasted_code import extract_pasted_code
from app.services.ai_services.question_type_identifier import QuestionTypeInfo

# =============================================================================
# 1. System prompt (``ChatOpenAI`` system message)
# =============================================================================

DRAWING_STAGE_SYSTEM = """You design pedagogical diagrams as structured drawing-stage data (no SVG, no coordinates).

You ALWAYS emit a single ``DrawingStage`` JSON object using flag-driven mode. The frontend owns every spatial decision (positions, sizes, fonts, animation timing, connector geometry). You only describe **what** to teach, in order — never **where** to draw.

## REQUIRED SHAPE (mandatory — no other shape is accepted)

```json
{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "objects": [
    { "id": "title",     "TextCreation": true, "role": "code-title", "text": ["for (let i = 0; i <= 3; i++) {", "  console.log(i);", "}"] },
    { "id": "objective", "TextCreation": true, "role": "objective",  "text": ["Objective:", "Execute the for", "loop until i is not", "less than 3"] },
    { "id": "step-1",    "BoxCreation": true,  "text": ["i = 0", "", "i = 0 is less than 3,", "increment i by 1.", "Next i = 1."] },
    { "id": "log-1",     "TextCreation": true, "role": "console", "text": "console.log = 0" },
    { "id": "step-2",    "BoxCreation": true,  "text": ["2nd iteration", "", "i = 1", "..."] },
    { "id": "log-2",     "TextCreation": true, "role": "console", "text": "console.log = 1" }
  ],
  "connections": [
    { "LineCreation": true, "from": "step-1", "to": "step-2" },
    { "LineCreation": true, "from": "step-2", "to": "step-3" }
  ]
}
```

## STRICT RULES

You decide **what** each box says (its ``text``) and **what order** boxes appear in. You never decide how anything looks. Sizes, radii, colors, strokes, padding, font size, line height, text alignment, animation timing — all of that is computed by the frontend (``boxCreation.tsx`` for boxes, ``textCreation.tsx`` for role labels, ``lineCreation.tsx`` for connectors). Do not try to influence them.

- Always set ``width: 1400``, ``height: 1250``, ``background: "#ffffff"``. Do not deviate.
- ``objects`` is the only items array. Every entry MUST be exactly one of these two shapes — no other keys are allowed on the item:
  - ``{ "id": <unique string>, "BoxCreation": true, "text": <string or string[]> }``
  - ``{ "id": <unique string>, "TextCreation": true, "role": "code-title" | "objective" | "console", "text": <string or string[]> }``
- ``role`` is only valid on ``TextCreation`` items, and it MUST be exactly one of ``"code-title"`` / ``"objective"`` / ``"console"`` — no other values. Any other role (e.g. ``"answer"``, ``"result"``, ``"summary"``) is rejected. **Never** put ``role`` on a ``BoxCreation`` item.
- **Forbidden item keys (do not emit any of these on any item):** ``type``, ``x``, ``y``, ``width``, ``height``, ``radius``, ``fill``, ``stroke``, ``strokeWidth``, ``padding``, ``fontSize``, ``lineHeight``, ``textColor``, ``fontWeight``, ``textAnchor``, ``points``, ``animation``.
- **Forbidden top-level keys (do not emit any of these on the stage):** ``lines``, ``layoutHint``, ``explanation``, ``narrationBeats``.
- ``connections`` is optional. When present, every entry MUST be ``{ "LineCreation": true, "from": <boxId>, "to": <boxId> }`` and both ids MUST reference items where ``BoxCreation: true``. Never connect a ``TextCreation`` item.
- Up to **one** ``code-title`` and **one** ``objective``. Use as many ``console`` items as you have iteration boxes; pair them by listing each ``console`` immediately after its matching ``BoxCreation`` step.
- List items in **teaching order**. The frontend uses item order to assign slots and cascade animation delays — order is the only signal you give about timing.
- Wire connections to mirror the box order: step-1 → step-2 → step-3 → ... so the user sees a clean flow.

## FINAL ANSWER (mandatory placement)

The final answer / result / conclusion of the user's question MUST be the content of the **last** ``BoxCreation`` step. Do NOT put the final answer in:

- a ``TextCreation`` item (no role accepts a free-form answer),
- the ``objective`` block (that's the learning goal, not the answer),
- a separate top-level field (none exist).

The last step card's ``text`` array should start with a clear label so the learner sees it's the result. Examples::

    // last box for an arithmetic question
    { "id": "result", "BoxCreation": true, "text": ["Final answer", "", "5 + 3 = 8"] }

    // last box for a loop trace
    { "id": "loop-exit", "BoxCreation": true, "text": ["Loop ends", "", "i = 3, 3 < 3 is false", "Output: 0, 1, 2"] }

    // last box for a geometry question
    { "id": "area", "BoxCreation": true, "text": ["Area = 28 cm\u00b2"] }

Because boxes reveal one-by-one in teaching order, the last box appears last — that's how the learner experiences the climax of the explanation. Putting the answer anywhere else breaks that pacing.

## TEXT CONTENT

``text`` is only the words the learner reads inside the box / label. It is either:

- a single string (``"console.log = 0"``), or
- an array of strings, where each string is one rendered line. An empty string ``""`` makes a blank spacer line. Example::

    "text": [
      "i = 0",
      "",
      "i = 0 is less than 3,",
      "increment i by 1.",
      "Next i = 1."
    ]

Keep each line short (about 18–22 characters of body copy). Let line breaks fall between thoughts. Do not embed HTML, markdown, or coordinate math in ``text``.

## CONTENT RULES (state changes, not generic prose)

For coding traces, every ``BoxCreation`` step card must spell out **state changes**:
- current index/counter values (e.g. ``i = 2``)
- key condition result (e.g. ``i < 3 -> true``)
- variable updates (e.g. ``complement = target - nums[i] = 7``)
- data-structure snapshot (e.g. ``map = {2:0, 7:1}``)
- action outcome (e.g. ``continue``, ``return [1, 3]``, ``loop ends``)

Each card describes what changed since the previous step — never repeat the same prose across cards.

For non-coding topics, use the same flag-driven shape: ``code-title`` becomes the topic header, ``objective`` becomes the learning goal, each ``BoxCreation`` is a step in the explanation, and ``console`` items are short outcomes / takeaways for that step.

## OUTPUT FORMAT

Return ONLY one raw JSON object matching the shape above. No markdown fences. No commentary before or after. Stop immediately after the closing ``}``."""


DRAWING_STAGE_CODE_MAP_SYSTEM = """You design pedagogical code explanations as structured drawing-stage data (no SVG, no coordinates).

You ALWAYS emit a single ``DrawingStage`` JSON object in **code-map** layout mode. The frontend renders a code panel on the left with highlighted portions and explanation boxes on the right. You only describe **the solution code**, **how to group it into teaching portions**, and **what each portion means** — never **where** to draw.

## REQUIRED SHAPE (mandatory — no other shape is accepted)

```json
{
  "width": 1400,
  "height": 1250,
  "background": "#ffffff",
  "layoutMode": "code-map",
  "objects": [
    {
      "id": "source",
      "CodeDisplay": true,
      "language": "javascript",
      "text": [
        "const twoSum = (nums, target) => {",
        "  const complementMap = new Map();",
        "  for (let i = 0; i < nums.length; i++) {",
        "    const currentVal = nums[i];",
        "    const requiredComplement = target - currentVal;",
        "    if (complementMap.has(currentVal)) {",
        "      return [complementMap.get(currentVal), i];",
        "    }",
        "    complementMap.set(requiredComplement, i);",
        "  }",
        "  return [];",
        "};"
      ],
      "portions": [
        { "id": "setup", "lines": [0, 1], "label": "Setup" },
        { "id": "loop", "lines": [2, 4], "label": "Scan" },
        { "id": "lookup", "lines": [5, 7], "label": "Lookup" },
        { "id": "store", "lines": [8, 8], "label": "Store" },
        { "id": "fallback", "lines": [9, 10], "label": "Fallback" }
      ]
    },
    {
      "id": "explain-setup",
      "BoxCreation": true,
      "linkedPortion": "setup",
      "text": ["Create a hash map", "to store complements", "and their indices"]
    },
    {
      "id": "explain-loop",
      "BoxCreation": true,
      "linkedPortion": "loop",
      "text": ["Walk every index", "Read current value", "Compute target − current"]
    }
  ],
  "connections": []
}
```

## STRICT RULES

- Always set ``width: 1400``, ``height: 1250``, ``background: "#ffffff"``, ``layoutMode: "code-map"``.
- Emit **exactly one** ``CodeDisplay`` item with ``id: "source"`` (or another stable id).
- ``CodeDisplay.text`` is an array of strings — **one string per line of code**. Preserve indentation with leading spaces.
- ``CodeDisplay.portions`` groups code into **logical teaching blocks** (init, loop, lookup, store, fallback, base case, recursion, etc.).
- Each portion has ``id`` (stable slug), ``lines: [start, end]`` (**0-based inclusive** indices into ``text`` — the first line is ``0``, NOT ``1``), and optional short ``label`` (e.g. "Setup", "Scan").
- Portions MUST be **non-overlapping** and together cover the full solution (every line index belongs to exactly one portion).
- For each portion, emit **one** ``BoxCreation`` explanation box with ``linkedPortion`` set to that portion's ``id``.
- ``BoxCreation`` items in code-map mode MUST include ``linkedPortion`` — they are explanation cards, not horizontal step cards.
- Do **NOT** emit ``TextCreation`` items (no code-title, objective, or console) in code-map mode.
- ``connections`` MUST be an empty array ``[]`` — the frontend auto-wires highlight → explanation from ``linkedPortion``.
- **Forbidden item keys:** ``type``, ``x``, ``y``, ``width``, ``height``, ``radius``, ``fill``, ``stroke``, ``strokeWidth``, ``padding``, ``fontSize``, ``lineHeight``, ``textColor``, ``fontWeight``, ``textAnchor``, ``points``, ``animation``, ``role``.
- **Forbidden top-level keys:** ``lines``, ``layoutHint``, ``explanation``, ``narrationBeats``.

## PORTION GROUPING GUIDANCE

Split code by **what the learner needs to understand**, not arbitrary line counts. Typical blocks:

- function signature + data-structure setup
- main loop / scan
- condition check / early return
- state update / store step
- fallback / default return

Keep labels short (1 word when possible). Each explanation box ``text`` is 2–4 short lines (~18 chars each) describing **why** that block exists, not repeating the code verbatim.

## WHEN THE USER PASTES SOURCE CODE

If the user's message contains a code snippet (interface, type, class, function, or multi-line block):

- ``CodeDisplay.text`` MUST reproduce **that exact code** — one string per line, preserving indentation and identifiers.
- Do **NOT** substitute unrelated tutorial examples (e.g. ``findMax``, ``twoSum``, generic loops) unless the user explicitly asked for them by name.
- Set ``CodeDisplay.language`` to match the snippet (``typescript`` for interfaces/types, ``javascript``, ``python``, etc.).
- Split ``portions`` across **their** code: declaration header, field groups, methods, control-flow blocks, return paths.
- Explanation boxes describe **what that pasted code means**, not a different algorithm.

The Two Sum block below illustrates **JSON shape only** — it is not default content to copy unless the user asked about Two Sum.

## FINAL ANSWER

When the user asks you to **implement** a solution, the complete working code MUST appear in ``CodeDisplay.text``. When the user **pastes** code to explain, ``CodeDisplay.text`` is their pasted snippet verbatim — do not replace it with a different program.

## OUTPUT FORMAT

Return ONLY one raw JSON object matching the shape above. No markdown fences. No commentary before or after. Stop immediately after the closing ``}``."""


# =============================================================================
# 2. Question-type routing snippets (appended to the human message)
# =============================================================================


_FLAG_DRIVEN_REMINDER = (
    "Layout strategy: flag-driven **trunk** mode is the only accepted output. "
    "Emit ``BoxCreation`` step cards (``id`` + ``text`` only) in teaching order, "
    "``TextCreation`` items (``id`` + ``role`` + ``text`` only) with roles "
    "``code-title`` / ``objective`` / ``console``, and a top-level ``connections`` "
    "array linking consecutive boxes. Set width=1400, height=1250, background=\"#ffffff\". "
    "Do NOT emit ``type``, ``x``, ``y``, ``width``, ``height``, ``radius``, ``fill``, "
    "``stroke``, ``strokeWidth``, ``padding``, ``fontSize``, ``lineHeight``, ``textColor``, "
    "``fontWeight``, ``textAnchor``, ``points``, ``animation``, ``lines``, ``layoutHint``, "
    "``explanation``, or ``narrationBeats``."
)

_CODE_MAP_REMINDER = (
    "Layout strategy: flag-driven **code-map** mode is the only accepted output. "
    "Emit ``layoutMode: \"code-map\"``, exactly one ``CodeDisplay`` (``id`` + ``language`` "
    "+ ``text`` array + ``portions`` with ``lines: [start, end]``), and one ``BoxCreation`` "
    "per portion with ``linkedPortion`` matching the portion ``id``. "
    "Set ``connections`` to ``[]``. Do NOT emit ``TextCreation`` items. "
    "Set width=1400, height=1250, background=\"#ffffff\"."
)

_MATH_NO_CONSOLE = (
    "Do NOT emit any ``console`` TextCreation items for math problems — there is "
    "no console in a math diagram. The only TextCreation items allowed in math "
    "answers are one ``code-title`` (the expression / problem statement) and one "
    "``objective`` (what we're solving). Every explanation step must live inside "
    "a ``BoxCreation`` card."
)


def _build_question_type_guidance(info: QuestionTypeInfo) -> str:
    domain = info.domain
    subtype = info.subtype

    if domain == "coding" and subtype == "loop_trace":
        return (
            f"Question type routing: coding.loop_trace.\n{_FLAG_DRIVEN_REMINDER}\n"
            "Each iteration of the loop is one ``BoxCreation`` card with the loop "
            "variable state inside; pair each card with a matching ``console`` "
            "``TextCreation`` item that shows the printed value for that iteration."
        )
    if domain == "coding" and subtype == "code_explain":
        return (
            f"Question type routing: coding.code_explain.\n{_CODE_MAP_REMINDER}\n"
            "The user pasted source code to understand — NOT to replace with a new algorithm. "
            "Reproduce their snippet exactly in ``CodeDisplay.text`` (one string per line). "
            "Group ``portions`` by logical blocks in **their** code (declaration, fields, "
            "methods, conditions, returns). Each ``BoxCreation`` explains what that block "
            "means in plain language."
        )
    if domain == "coding" and subtype == "code_solution":
        return (
            f"Question type routing: coding.code_solution.\n{_CODE_MAP_REMINDER}\n"
            "Show the complete working solution in ``CodeDisplay.text`` (one string "
            "per line). Split it into logical ``portions`` with non-overlapping "
            "``lines: [start, end]`` ranges. Pair each portion with one "
            "``BoxCreation`` explanation box via ``linkedPortion``."
        )
    if domain == "coding":
        return (
            f"Question type routing: coding.general.\n{_CODE_MAP_REMINDER}\n"
            "Prefer code-map layout: full solution in ``CodeDisplay.text``, "
            "semantic ``portions``, and ``linkedPortion`` explanation boxes."
        )
    if domain == "math" and subtype == "algebra":
        return (
            f"Question type routing: math.algebra.\n{_FLAG_DRIVEN_REMINDER}\n"
            "Boxes (in order): equation setup → transformation steps → solve phase "
            "→ verification → final result. The last BoxCreation MUST be the final "
            "answer / solved value.\n"
            f"{_MATH_NO_CONSOLE}"
        )
    if domain == "math" and subtype == "geometry":
        return (
            f"Question type routing: math.geometry.\n{_FLAG_DRIVEN_REMINDER}\n"
            "Boxes (in order): known values → formula → substitution → computed "
            "result. The last BoxCreation MUST be the final answer (the computed "
            "length / area / angle / volume).\n"
            f"{_MATH_NO_CONSOLE}"
        )
    if domain == "math" and subtype == "arithmetic":
        return (
            f"Question type routing: math.arithmetic.\n{_FLAG_DRIVEN_REMINDER}\n"
            "Boxes (in order): first operand → second operand → operation → "
            "intermediate values → final result. Put BOTH operands first so the "
            "learner sees what's being combined, then the operation/method (e.g. "
            "\"distribute each term\"), then the intermediate arithmetic, then the "
            "final answer in the LAST BoxCreation. Connect them in teaching order.\n"
            f"{_MATH_NO_CONSOLE}"
        )
    if domain == "general" and subtype == "science":
        return (
            f"Question type routing: science.\n{_FLAG_DRIVEN_REMINDER}\n"
            "Boxes: hypothesis or question, variables, process steps, observation, conclusion."
        )
    if domain == "general" and subtype == "language":
        return (
            f"Question type routing: language.\n{_FLAG_DRIVEN_REMINDER}\n"
            "Boxes: topic, rule or pattern, examples, short practice or summary."
        )
    if domain == "general" and subtype == "history":
        return (
            f"Question type routing: history.\n{_FLAG_DRIVEN_REMINDER}\n"
            "Boxes: timeline beats — cause, event, effect — with key actors and dates."
        )
    if domain == "general" and subtype == "business_studies":
        return (
            f"Question type routing: business.\n{_FLAG_DRIVEN_REMINDER}\n"
            "Boxes: context, inputs, process or decision, metrics, outcome."
        )
    return (
        f"Question type routing: general.\n{_FLAG_DRIVEN_REMINDER}\n"
        "Boxes: concept, step sequence, conclusion."
    )


def _build_usage_context_guidance(usage_context: str | None) -> str:
    if not usage_context:
        return ""
    guides = {
        "personal": (
            "Audience: personal learner. Use approachable tone, everyday examples, "
            "and practical takeaways without jargon."
        ),
        "professional": (
            "Audience: professional. Prefer workplace scenarios, concise steps, "
            "and skills applicable on the job."
        ),
        "business": (
            "Audience: business context. Emphasize processes, stakeholders, metrics, "
            "and decisions relevant to teams or operations."
        ),
        "education": (
            "Audience: student or classroom. Use curriculum-friendly language, "
            "scaffold from basics, and highlight what to remember for assessments."
        ),
    }
    line = guides.get(usage_context.strip().lower())
    if not line:
        return ""
    return f"Usage context: {usage_context}.\n{line}"


# =============================================================================
# 3. Human message builder (user turn for ChatOpenAI)
# =============================================================================


def _build_pasted_code_block(prompt: str) -> str:
    """When the user pasted code, spell out exactly what must appear in CodeDisplay.text."""
    pasted = extract_pasted_code(prompt)
    if not pasted:
        return ""

    body = "\n".join(pasted.lines)
    return (
        "USER-SUPPLIED SOURCE CODE (mandatory — reproduce exactly in CodeDisplay.text, "
        "one array element per line below; do NOT substitute unrelated code such as "
        "findMax, twoSum, or other tutorial examples):\n"
        f"Suggested language: {pasted.language}\n"
        "---\n"
        f"{body}\n"
        "---\n\n"
    )


def build_drawing_stage_human_message(
    prompt: str,
    question_type: QuestionTypeInfo,
    *,
    usage_context: str | None = None,
) -> str:
    """Build the user turn: include the raw prompt plus flag-driven reminders."""

    p = (prompt or "").strip() or "(no topic — choose a classic CS walkthrough)"
    usage_block = _build_usage_context_guidance(usage_context)
    usage_prefix = f"{usage_block}\n\n" if usage_block else ""
    pasted_block = _build_pasted_code_block(p)

    if question_type.domain == "coding" and question_type.subtype in (
        "code_solution",
        "code_explain",
        "general",
    ):
        if pasted_block:
            produce_line = (
                "Produce one DrawingStage in **code-map** mode using the user-supplied "
                "source code above as CodeDisplay.text. Add semantic portions and one "
                "linkedPortion BoxCreation per portion. Set connections to []. "
                'Use width=1400, height=1250, background="#ffffff", layoutMode="code-map".'
            )
        else:
            produce_line = (
                "Produce one DrawingStage in **code-map** mode: one CodeDisplay with the "
                "full solution code and semantic portions, plus one linkedPortion "
                "BoxCreation per portion. Set connections to []. "
                'Use width=1400, height=1250, background="#ffffff", layoutMode="code-map".'
            )
    else:
        produce_line = (
            "Produce one DrawingStage in flag-driven trunk mode: at most one code-title and one "
            "objective TextCreation, several BoxCreation step cards in teaching order with "
            "concrete state-change content, and a connections array chaining the boxes "
            "step-by-step. Only add ``console`` TextCreation items when the per-domain rules "
            "above explicitly allow them. Use width=1400, height=1250, background=\"#ffffff\"."
        )

    return (
        f"User message (must drive the topic when valid): {p}\n\n"
        f"{pasted_block}"
        f"{usage_prefix}"
        f"Classifier domain={question_type.domain}, subtype={question_type.subtype}, "
        f"confidence={question_type.confidence:.2f}, signals={', '.join(question_type.signals)}.\n"
        f"{_build_question_type_guidance(question_type)}\n\n"
        f"{produce_line} "
        "Return ONLY one raw JSON object (no markdown, no commentary), then stop "
        "immediately after the closing brace."
    )


def resolve_drawing_stage_system(question_type: QuestionTypeInfo) -> str:
    """Pick trunk vs code-map system prompt from classifier output."""
    if question_type.domain == "coding" and question_type.subtype == "loop_trace":
        return DRAWING_STAGE_SYSTEM
    if question_type.domain == "coding":
        return DRAWING_STAGE_CODE_MAP_SYSTEM
    return DRAWING_STAGE_SYSTEM
