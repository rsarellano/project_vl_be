"""Coding pedagogy for AI lecture generation (editable stage objects)."""

CODING_LECTURE_PEDAGOGY = """
## Subject pedagogy: CODING (required)

Programming lectures use the **same editable stage objects** as other lectures
(code panels, boxes, arrows, text) — not AI Tutor portion cards or "How this works".

### What every coding lecture needs
- Prefer 5–7 slides: hook → concept → worked_example → practice → check → summary.
- Put a **complete, runnable program** in ``equation`` as plain multiline text
  (no markdown fences) on concept, worked_example, practice, and check slides.
  Optionally also fill ``code_lines`` (one string per source line) mirroring equation.
- ``scene_hint.archetype`` MUST be ``code_walkthrough`` (use ``code_flow`` only for
  explicit Input → Transform → Output demos). Never ``basic_boxes`` or ``concept_comparison``.
- ``scene_hint.code_language``: javascript, python, typescript, etc. matching the sample.

### steps / callout / explanation
- ``steps``: 2–3 short stage boxes that name real code blocks
  (e.g. "Setup — create the lookup map", "Loop — scan each number").
  Never filler like "Frame the concept" / "Show the key move".
- ``callout``: one punchy tip ("Watch off-by-one", "Hash map = O(1) lookup").
- ``explanation``: the big idea in 1–3 sentences (mental model).
- ``narration``: what the educator says while pointing at the stage.
- On the check slide, ``checkpoint`` is a multiple-choice question about the sample
  (complexity, off-by-one, what a line does) — not a freeform essay.

### Sample quality
- Teach the educator's topic with a concrete function students could run.
- Prefer the language implied by the prompt; default to javascript if unclear.
- Do NOT invent train / motion scenes. Do NOT leave equation empty on code slides.
"""
