"""Sample ``DrawingStage`` payloads (flag-driven only).

Static fixtures for contract / frontend testing without the LLM. Served by
``GET /api/answers/samples/while-loop`` and ``GET /api/answers/samples/two-sum``.
"""

from __future__ import annotations

from app.schemas.infographics_schema import DrawingStage


def get_while_loop_stage() -> DrawingStage:
    """Return a validated flag-driven ``DrawingStage`` tracing ``while (i < 3)``."""

    payload: dict = {
        "width": 1400,
        "height": 1250,
        "background": "#ffffff",
        "objects": [
            {
                "id": "code-title",
                "TextCreation": True,
                "role": "code-title",
                "text": ["let i = 0;", "while (i < 3) {", "  console.log(i);", "  i++;", "}"],
            },
            {
                "id": "objective",
                "TextCreation": True,
                "role": "objective",
                "text": [
                    "Objective:",
                    "Trace the while loop",
                    "until i is no longer",
                    "less than 3.",
                ],
            },
            {
                "id": "step-1",
                "BoxCreation": True,
                "text": [
                    "i = 0",
                    "",
                    "0 < 3 is true so",
                    "the body runs and",
                    "i++ makes i = 1.",
                ],
            },
            {
                "id": "log-1",
                "TextCreation": True,
                "role": "console",
                "text": "console.log = 0",
            },
            {
                "id": "step-2",
                "BoxCreation": True,
                "text": [
                    "2nd iteration",
                    "",
                    "i = 1",
                    "",
                    "1 < 3 is true so",
                    "the body runs and",
                    "i++ makes i = 2.",
                ],
            },
            {
                "id": "log-2",
                "TextCreation": True,
                "role": "console",
                "text": "console.log = 1",
            },
            {
                "id": "step-3",
                "BoxCreation": True,
                "text": [
                    "3rd iteration",
                    "",
                    "i = 2",
                    "",
                    "2 < 3 is true so",
                    "the body runs and",
                    "i++ makes i = 3.",
                ],
            },
            {
                "id": "log-3",
                "TextCreation": True,
                "role": "console",
                "text": "console.log = 2",
            },
            {
                "id": "step-4",
                "BoxCreation": True,
                "text": [
                    "final check",
                    "",
                    "i = 3",
                    "3 < 3 is false so",
                    "the loop exits.",
                ],
            },
        ],
        "connections": [
            {"LineCreation": True, "from": "step-1", "to": "step-2"},
            {"LineCreation": True, "from": "step-2", "to": "step-3"},
            {"LineCreation": True, "from": "step-3", "to": "step-4"},
        ],
    }

    return DrawingStage.model_validate(payload)


def get_two_sum_code_map_stage() -> DrawingStage:
    """Return a validated code-map ``DrawingStage`` for Two Sum (no LLM)."""

    payload: dict = {
        "width": 1400,
        "height": 1250,
        "background": "#ffffff",
        "layoutMode": "code-map",
        "objects": [
            {
                "id": "source",
                "CodeDisplay": True,
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
                    "};",
                ],
                "portions": [
                    {"id": "setup", "lines": [0, 1], "label": "Setup"},
                    {"id": "loop", "lines": [2, 4], "label": "Scan"},
                    {"id": "lookup", "lines": [5, 7], "label": "Lookup"},
                    {"id": "store", "lines": [8, 8], "label": "Store"},
                    {"id": "fallback", "lines": [9, 10], "label": "Fallback"},
                ],
            },
            {
                "id": "explain-setup",
                "BoxCreation": True,
                "linkedPortion": "setup",
                "text": [
                    "Create a hash map",
                    "to store each complement",
                    "and its index",
                ],
            },
            {
                "id": "explain-loop",
                "BoxCreation": True,
                "linkedPortion": "loop",
                "text": [
                    "Walk every index",
                    "Read current value",
                    "Compute target − current",
                ],
            },
            {
                "id": "explain-lookup",
                "BoxCreation": True,
                "linkedPortion": "lookup",
                "text": [
                    "If current value",
                    "already in map →",
                    "return both indices",
                ],
            },
            {
                "id": "explain-store",
                "BoxCreation": True,
                "linkedPortion": "store",
                "text": [
                    "Otherwise store",
                    "complement → index",
                    "for future hits",
                ],
            },
            {
                "id": "explain-fallback",
                "BoxCreation": True,
                "linkedPortion": "fallback",
                "text": [
                    "No pair found",
                    "after full scan",
                    "return empty array",
                ],
            },
        ],
        "connections": [],
    }

    return DrawingStage.model_validate(payload)
