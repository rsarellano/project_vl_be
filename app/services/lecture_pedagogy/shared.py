"""Shared lecture pedagogy — teaching arc + stage showcase rules.

Topic packs (algebra, trigonometry, …) live beside this and are selected separately.
"""

LECTURE_PEDAGOGY = """
## Shared pedagogy (required arc)
Build a classroom-ready lesson that feels complete and impressive — not a thin outline.
Prefer 5–8 slides unless the educator asks for a different length.
Use these slide_role values in order when they fit the topic:
1. hook — why it matters / prior knowledge spark
2. concept — formal definition or core idea
3. worked_example — step-by-step solution (show every move)
4. practice — a second example students try mentally
5. check — common mistake + correct fix
6. summary — takeaways + when to use this idea

Every slide must be teachable alone:
- narration: full educator script (what to SAY) — 3–6 spoken sentences, concrete.
- explanation: short on-screen idea (1–3 sentences), not a transcript dump.
- equation: KaTeX-friendly math / code when relevant; otherwise "".
- callout: a punchy tip, warning, or "watch for…" (shown as a stage callout).
- steps: 2–3 VERY short stage steps (≤12 words each) that appear as animated boxes.
  For worked_example / practice, steps MUST show the real method (not filler).

## Stage showcase (critical)
Project VL stages support boxes, arrows, shapes, text, and motion.
Write content that FILLS a rich stage:
- Prefer concrete numbers and worked math/code the stage can display.
- Avoid vague titles like "Introduction" — be specific.
- For relative-motion word problems only, visual_type may be "trains".
- Otherwise use "equation", "graph", "triangle", or "circle" to hint at shape accents.
"""
