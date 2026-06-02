"""Backward-compatible re-exports — prefer ``drawing_stage`` package.

One file per subtype, e.g.:
  drawing_stage/math/algebra.py
  drawing_stage/science/biology.py
  drawing_stage/coding/code_solution.py
"""

from app.services.ai_services.drawing_stage import (
    DRAWING_STAGE_CODE_MAP_SYSTEM,
    DRAWING_STAGE_MATH_SYSTEM,
    DRAWING_STAGE_SCIENCE_SYSTEM,
    DRAWING_STAGE_SYSTEM,
    build_drawing_stage_human_message,
    resolve_drawing_stage_system,
)

__all__ = [
    "DRAWING_STAGE_CODE_MAP_SYSTEM",
    "DRAWING_STAGE_SYSTEM",
    "DRAWING_STAGE_MATH_SYSTEM",
    "DRAWING_STAGE_SCIENCE_SYSTEM",
    "build_drawing_stage_human_message",
    "resolve_drawing_stage_system",
]
