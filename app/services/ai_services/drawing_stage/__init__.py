"""Per-subtype drawing stage prompts.

Edit the file for the topic you care about:

  coding/code_solution.py   coding/code_explain.py   coding/loop_trace.py
  math/algebra.py           math/geometry.py         math/arithmetic.py
  science/biology.py        science/chemistry.py     science/physics.py

Classifier → ``(domain, subtype)`` → ``registry.get_subtype_prompt``.
"""

from .coding.code_solution import PROMPT as CODING_CODE_SOLUTION_PROMPT
from .math.algebra import PROMPT as MATH_ALGEBRA_PROMPT
from .registry import get_subtype_prompt, list_registered_subtypes
from .router import build_drawing_stage_human_message, resolve_drawing_stage_system
from .science.biology import PROMPT as SCIENCE_BIOLOGY_PROMPT

# Legacy aliases
DRAWING_STAGE_CODE_MAP_SYSTEM = CODING_CODE_SOLUTION_PROMPT.system
DRAWING_STAGE_MATH_SYSTEM = MATH_ALGEBRA_PROMPT.system
DRAWING_STAGE_SYSTEM = MATH_ALGEBRA_PROMPT.system
DRAWING_STAGE_SCIENCE_SYSTEM = SCIENCE_BIOLOGY_PROMPT.system

__all__ = [
    "build_drawing_stage_human_message",
    "resolve_drawing_stage_system",
    "get_subtype_prompt",
    "list_registered_subtypes",
    "DRAWING_STAGE_CODE_MAP_SYSTEM",
    "DRAWING_STAGE_SYSTEM",
    "DRAWING_STAGE_MATH_SYSTEM",
    "DRAWING_STAGE_SCIENCE_SYSTEM",
]
